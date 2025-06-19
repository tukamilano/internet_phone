# voice_chat.py

import socket
import subprocess
import threading
import sys

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

def send_audio(sock):
    """マイクから音声を録音し、ソケット経由で送信する"""
    # 'rec' コマンドをサブプロセスとして起動
    # stdout=subprocess.PIPE で、録音された音声データがパイプに出力される
    rec_process = subprocess.Popen(['rec'] + AUDIO_FORMAT, stdout=subprocess.PIPE)
    print("音声送信スレッドを開始しました。")

    try:
        while True:
            # recプロセスから音声データを読み込む
            audio_data = rec_process.stdout.read(BUFFER_SIZE)
            if not audio_data:
                break
            # ソケットにデータを送信
            sock.sendall(audio_data)
    except (BrokenPipeError, ConnectionResetError):
        print("送信中に接続が切れました。")
    except Exception as e:
        print(f"send_audioでエラーが発生しました: {e}")
    finally:
        print("音声送信スレッドを終了します。")
        rec_process.terminate() # recプロセスを終了

def recv_audio(sock):
    """ソケットから音声データを受信し、スピーカーで再生する"""
    # 'play' コマンドをサブプロセスとして起動
    # stdin=subprocess.PIPE で、パイプ経由で音声データをプロセスに渡せる
    play_process = subprocess.Popen(['play'] + AUDIO_FORMAT, stdin=subprocess.PIPE)
    print("音声受信スレッドを開始しました。")

    try:
        while True:
            # ソケットからデータを受信
            audio_data = sock.recv(BUFFER_SIZE)
            if not audio_data:
                break
            # playプロセスの標準入力にデータを書き込む
            play_process.stdin.write(audio_data)
    except (BrokenPipeError, ConnectionResetError):
        print("受信中に接続が切れました。")
    except Exception as e:
        print(f"recv_audioでエラーが発生しました: {e}")
    finally:
        print("音声受信スレッドを終了します。")
        play_process.terminate() # playプロセスを終了


def main():
    """メイン処理。引数に応じてサーバーまたはクライアントとして動作する。"""
    if len(sys.argv) < 2:
        print(f"使い方: python {sys.argv[0]} [server <port> | client <host> <port>]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'server':
        if len(sys.argv) != 3:
            print(f"サーバーモードの使い方: python {sys.argv[0]} server <port>")
            sys.exit(1)

        port = int(sys.argv[2])

        # サーバーソケットの作成
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', port))
            server_socket.listen(1)
            print(f"サーバーがポート {port} で接続を待機しています...")

            # クライアントからの接続を待つ
            conn, addr = server_socket.accept()
            with conn:
                print(f"クライアント {addr} が接続しました。")

                # 送信・受信スレッドの開始
                send_thread = threading.Thread(target=send_audio, args=(conn,))
                recv_thread = threading.Thread(target=recv_audio, args=(conn,))

                send_thread.start()
                recv_thread.start()

                send_thread.join()
                recv_thread.join()

    elif mode == 'client':
        if len(sys.argv) != 4:
            print(f"クライアントモードの使い方: python {sys.argv[0]} client <host> <port>")
            sys.exit(1)

        host = sys.argv[2]
        port = int(sys.argv[3])

        # クライアントソケットの作成とサーバーへの接続
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.connect((host, port))
                print(f"サーバー {host}:{port} に接続しました。")

                # 送信・受信スレッドの開始
                send_thread = threading.Thread(target=send_audio, args=(sock,))
                recv_thread = threading.Thread(target=recv_audio, args=(sock,))

                send_thread.start()
                recv_thread.start()

                send_thread.join()
                recv_thread.join()

            except ConnectionRefusedError:
                print(f"接続が拒否されました。サーバー {host}:{port} が起動しているか確認してください。")
            except Exception as e:
                print(f"クライアントでエラーが発生しました: {e}")
    else:
        print(f"不明なモード: {mode}")
        print(f"使い方: python {sys.argv[0]} [server <port> | client <host> <port>]")
        sys.exit(1)

    print("プログラムを終了します。")

if __name__ == '__main__':
    main()