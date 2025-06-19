import socket
import subprocess
import threading
import sys
import audioop
import time
import matplotlib.pyplot as plt

# 定数
BUFFER_SIZE = 512
# SoXのオーディオ設定（C言語版と同一）
AUDIO_FORMAT = [
    '-t', 'raw',    # タイプ: raw
    '-b', '16',     # ビット深度: 16-bit
    '-c', '1',      # チャンネル数: 1 (mono)
    '-e', 's',      # エンコーディング: signed-integer
    '-r', '44100',  # サンプルレート: 44.1kHz
    '-',            # 標準入出力を使用
]

def play_beep():
    """0.1秒のビープ音を再生する"""
    try:
        subprocess.run(
            ['play', '-n', 'synth', '0.3', 'sine', '1000', 'vol', '0.1'],
            check=True,
            capture_output=True
        )
        print("ビープ音を再生しました。")
    except subprocess.CalledProcessError as e:
        print(f"ビープ音の再生に失敗しました: {e}")
    except FileNotFoundError:
        print("SoXがインストールされていません。ビープ音を再生できません。")


def send_audio(sock):
    """マイクから音声を録音し、ソケット経由で送信する"""
    rec_process = subprocess.Popen(['rec'] + AUDIO_FORMAT, stdout=subprocess.PIPE)
    print("音声送信スレッドを開始しました。")

    try:
        while True:
            data = rec_process.stdout.read(BUFFER_SIZE)
            if not data:
                break
            sock.sendall(data)
    except (BrokenPipeError, ConnectionResetError):
        print("送信中に接続が切れました。")
    except Exception as e:
        print(f"send_audioでエラーが発生しました: {e}")
    finally:
        rec_process.terminate()
        print("送信スレッド終了")


def recv_audio(sock, amplitudes, timestamps, duration=10.0):
    """ソケットから音声データを受信し、スピーカーで再生しつつ振幅を記録"""
    play_process = subprocess.Popen(['play'] + AUDIO_FORMAT, stdin=subprocess.PIPE)
    print("音声受信スレッドを開始しました。")

    start_time = None
    try:
        while True:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                break
            now = time.time()
            if start_time is None:
                start_time = now
            elapsed = now - start_time
            if elapsed > duration:
                print(f"{duration}秒の記録完了")
                break
            # RMS振幅を記録
            rms = audioop.rms(data, 2)
            amplitudes.append(rms)
            timestamps.append(elapsed)
            # 再生
            play_process.stdin.write(data)
    except (BrokenPipeError, ConnectionResetError):
        print("受信中に接続が切れました。")
    except Exception as e:
        print(f"recv_audioでエラー: {e}")
    finally:
        play_process.terminate()
        print("受信スレッド終了")
        sock.close()


def plot_wave(amplitudes, timestamps):
    """メインスレッドで振幅をプロット"""
    if not amplitudes:
        print("プロットするデータがありません。")
        return
    plt.figure(figsize=(8, 4))
    plt.plot(timestamps, amplitudes)
    plt.xlabel("Time (s)")
    plt.ylabel("RMS amplitude")
    plt.title("Amplitude record")
    plt.grid(True)
    plt.tight_layout()
    plt.show()



def main():
    if len(sys.argv) < 2:
        print(f"使い方: python {sys.argv[0]} [server <port> | client <host> <port>]")
        return

    mode = sys.argv[1]
    amplitudes = []
    timestamps = []

    if mode == 'server':
        port = int(sys.argv[2])
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', port))
            s.listen(1)
            print(f"サーバー待機: ポート {port}")
            conn, addr = s.accept()
            print(f"クライアント接続: {addr}")
            play_beep()
            sender = threading.Thread(target=send_audio, args=(conn,), daemon=True)
            receiver = threading.Thread(target=recv_audio, args=(conn, amplitudes, timestamps), daemon=True)
            sender.start()
            receiver.start()
            receiver.join()
            sender.join()

    elif mode == 'client':
        host, port = sys.argv[2], int(sys.argv[3])
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((host, port))
                print(f"接続成功: {host}:{port}")
                sender = threading.Thread(target=send_audio, args=(s,), daemon=True)
                receiver = threading.Thread(target=recv_audio, args=(s, amplitudes, timestamps), daemon=True)
                sender.start()
                receiver.start()
                receiver.join()
                sender.join()
            except Exception as e:
                print(f"接続エラー: {e}")
                return
    else:
        print("モード指定エラー")
        return

    # メインスレッドでプロット
    plot_wave(amplitudes, timestamps)

if __name__ == '__main__':
    main()
