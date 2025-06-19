
#!/usr/bin/env python3
"""
遅延測定機能付き音声チャット
クライアントが定期的にタイムスタンプを送信し、サーバーで遅延を測定
"""

import socket
import subprocess
import threading
import sys
import time
import struct
import signal

# 定数
BUFFER_SIZE = 512
LATENCY_TEST_INTERVAL = 3.0  # 遅延測定間隔（秒）

# SoXのオーディオ設定
AUDIO_FORMAT = [
    '-t', 'raw',
    '-b', '16', 
    '-c', '1',
    '-e', 's',
    '-r', '44100',
    '-',
]

class LatencyMeasurement:
    def __init__(self):
        self.latencies = []
        self.last_test_time = 0
        
    def add_measurement(self, latency):
        """遅延測定値を追加"""
        self.latencies.append(latency)
        print(f"遅延: {latency*1000:.1f} ms (測定回数: {len(self.latencies)})")
        
    def show_stats(self):
        """統計情報を表示"""
        if not self.latencies:
            print("遅延測定データがありません")
            return
            
        avg = sum(self.latencies) / len(self.latencies)
        min_lat = min(self.latencies)
        max_lat = max(self.latencies)
        
        print(f"\n=== 遅延測定統計 ===")
        print(f"測定回数: {len(self.latencies)}")
        print(f"平均遅延: {avg*1000:.1f} ms")
        print(f"最小遅延: {min_lat*1000:.1f} ms") 
        print(f"最大遅延: {max_lat*1000:.1f} ms")
        
        if avg < 0.05:
            print("評価: 非常に良好 (50ms未満)")
        elif avg < 0.15:
            print("評価: 許容範囲 (150ms未満)")
        else:
            print("評価: 改善が必要 (150ms以上)")

# グローバル変数
latency_tracker = LatencyMeasurement()
should_exit = False

def signal_handler(signum, frame):
    """Ctrl+Cハンドラー"""
    global should_exit
    print("\n音声チャットを終了します...")
    should_exit = True
    latency_tracker.show_stats()

def create_latency_packet():
    """遅延測定用パケットを作成"""
    # マジックバイト (0xFF, 0xFE) + タイムスタンプ (8バイト)
    timestamp = struct.pack('>d', time.time())
    return b'\xFF\xFE' + timestamp

def extract_latency_packet(data):
    """データから遅延測定パケットを抽出"""
    if len(data) >= 10 and data[0:2] == b'\xFF\xFE':
        try:
            timestamp = struct.unpack('>d', data[2:10])[0]
            return timestamp, data[10:]  # タイムスタンプと残りのデータを返す
        except struct.error:
            pass
    return None, data

def send_audio(sock, is_client=False):
    """音声送信スレッド"""
    global should_exit
    
    rec_process = subprocess.Popen(['rec'] + AUDIO_FORMAT, stdout=subprocess.PIPE)
    print("音声送信開始")
    
    last_latency_test = time.time()
    
    try:
        while not should_exit:
            # クライアントの場合、定期的に遅延測定パケットを送信
            if is_client and (time.time() - last_latency_test) >= LATENCY_TEST_INTERVAL:
                latency_packet = create_latency_packet()
                sock.sendall(latency_packet)
                last_latency_test = time.time()
                print("遅延測定パケット送信")
            
            # 音声データを読み込んで送信
            audio_data = rec_process.stdout.read(BUFFER_SIZE)
            if not audio_data:
                break
            sock.sendall(audio_data)
            
    except (BrokenPipeError, ConnectionResetError, OSError):
        print("送信接続が切断されました")
    finally:
        rec_process.terminate()
        print("音声送信終了")

def recv_audio(sock, is_server=False):
    """音声受信スレッド"""
    global should_exit
    
    play_process = subprocess.Popen(['play'] + AUDIO_FORMAT, stdin=subprocess.PIPE)
    print("音声受信開始")
    
    buffer = b''
    
    try:
        while not should_exit:
            # データを受信
            try:
                data = sock.recv(BUFFER_SIZE)
            except OSError:
                break
                
            if not data:
                break
                
            buffer += data
            
            # バッファから遅延測定パケットを検出・処理
            while len(buffer) >= 10:
                timestamp, remaining = extract_latency_packet(buffer)
                if timestamp is not None:
                    # 遅延計算
                    latency = time.time() - timestamp
                    latency_tracker.add_measurement(latency)
                    buffer = remaining
                else:
                    # 音声データとして処理
                    chunk_size = min(len(buffer), BUFFER_SIZE)
                    audio_chunk = buffer[:chunk_size]
                    play_process.stdin.write(audio_chunk)
                    play_process.stdin.flush()
                    buffer = buffer[chunk_size:]
                    break
                    
    except (BrokenPipeError, ConnectionResetError, OSError):
        print("受信接続が切断されました")
    finally:
        play_process.terminate()
        print("音声受信終了")

def main():
    global should_exit
    
    signal.signal(signal.SIGINT, signal_handler)
    
    if len(sys.argv) < 2:
        print(f"使い方: python {sys.argv[0]} [server <port> | client <host> <port>]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'server':
        if len(sys.argv) != 3:
            print(f"サーバーモード: python {sys.argv[0]} server <port>")
            sys.exit(1)

        port = int(sys.argv[2])
        
        print(f"遅延測定機能付きサーバーを開始 (ポート: {port})")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', port))
            server_socket.listen(1)
            print("クライアントの接続を待機中...")

            try:
                conn, addr = server_socket.accept()
                print(f"クライアント {addr} が接続しました")
                
                with conn:
                    # 送信・受信スレッドを開始
                    send_thread = threading.Thread(target=send_audio, args=(conn, False))
                    recv_thread = threading.Thread(target=recv_audio, args=(conn, True))

                    send_thread.start()
                    recv_thread.start()

                    send_thread.join()
                    recv_thread.join()
                    
            except OSError:
                pass

    elif mode == 'client':
        if len(sys.argv) != 4:
            print(f"クライアントモード: python {sys.argv[0]} client <host> <port>")
            sys.exit(1)

        host = sys.argv[2]
        port = int(sys.argv[3])
        
        print(f"遅延測定機能付きクライアントを開始")
        print(f"接続先: {host}:{port}")

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((host, port))
                print("サーバーに接続しました")
                print(f"{LATENCY_TEST_INTERVAL}秒ごとに遅延を測定します")

                # 送信・受信スレッドを開始
                send_thread = threading.Thread(target=send_audio, args=(sock, True))
                recv_thread = threading.Thread(target=recv_audio, args=(sock, False))

                send_thread.start()
                recv_thread.start()

                send_thread.join()  
                recv_thread.join()

        except ConnectionRefusedError:
            print(f"接続拒否: サーバー {host}:{port} が起動していません")
        except OSError as e:
            print(f"接続エラー: {e}")

    else:
        print(f"不明なモード: {mode}")
        sys.exit(1)

    print("プログラム終了")

if __name__ == '__main__':
    main()