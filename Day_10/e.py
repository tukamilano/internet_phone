import socket
import subprocess
import threading
import sys
import audioop
import time
import matplotlib.pyplot as plt
import struct
from collections import deque
import numpy as np

# 定数
BUFFER_SIZE = 512
# SoXのオーディオ設定（C言語版と同一）
AUDIO_FORMAT = [
    '-t', 'raw',    # タイプ: raw
    '-b', '16',     # ビット深度: 16-bit
    '-c', '1',      # チャンネル数: 1 (mono)
    '-e', 's',      # エンコーディング: signed-integer
    '-r', '48000',  # サンプルレート: 48kHz
    '-',            # 標準入出力を使用
]

class EchoCanceller:
    def __init__(self, sample_rate=48000, max_delay_s=0.5):
        self.sample_rate = sample_rate
        self.max_delay_samples = int(max_delay_s * sample_rate)

        # 送信音声の履歴(相互相関用)
        self.sent_audio_buffer = deque(maxlen=self.max_delay_samples * 2)

        # 受信音声バッファ
        self.received_audio_buffer = deque(maxlen=self.max_delay_samples * 2)

        self.estimated_delay = 0
        self.lock = threading.Lock()
        self.process_count = 0  # 処理頻度制御用

        self.gain = 1

    def add_sent_audio(self, audio_data):
        """送信音声データを追加"""
        with self.lock:
            # バイトデータを16bit整数配列に変換
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            self.sent_audio_buffer.extend(samples)

    def process_received_audio(self, audio_data):
        """受信音声を処理し、遅延を推定"""
        with self.lock:
            # バイトデータを16bit整数配列に変換
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            self.received_audio_buffer.extend(samples)

            # 処理頻度を下げる（50回に1回のみ実行）
            self.process_count += 1
            if (self.process_count % 50 == 0 and 
                len(self.received_audio_buffer) >= self.max_delay_samples * 2 and 
                len(self.sent_audio_buffer) >= self.max_delay_samples * 2):
                self.estimate_delay()

        return audio_data # 処理後のデータを返す
    
    def estimate_delay(self):
        """FFTを使った高速相互相関による遅延推定"""
        window_size = 8192
        if len(self.sent_audio_buffer) < window_size or len(self.received_audio_buffer) < window_size:
            return
        
        sent_samples = np.array(list(self.sent_audio_buffer)[-window_size:], dtype=np.float32)
        received_samples = np.array(list(self.received_audio_buffer)[-window_size:], dtype=np.float32)
        
        # 平均を引く（DC成分除去）
        sent_samples = sent_samples - np.mean(sent_samples)
        received_samples = received_samples - np.mean(received_samples)
        
        # FFTベースの相互相関計算
        correlation_length = len(sent_samples) + len(received_samples) - 1
        fft_size = 2 ** int(np.ceil(np.log2(correlation_length)))
        
        sent_fft = np.fft.rfft(sent_samples, fft_size)
        received_fft = np.fft.rfft(received_samples, fft_size)
        
        cross_correlation_fft = sent_fft.conj() * received_fft
        correlation = np.fft.irfft(cross_correlation_fft, fft_size)
        correlation = correlation[:correlation_length]
        
        # 正規化（重要！）
        norm = np.sqrt(np.sum(sent_samples**2) * np.sum(received_samples**2))
        if norm > 0:
            correlation = correlation / norm
        
        max_corr_index = np.argmax(np.abs(correlation))
        correlation_center = len(correlation) // 2
        delay_samples = max_corr_index - correlation_center
        
        if 0 <= delay_samples <= self.max_delay_samples:
            self.estimated_delay = delay_samples
            delay_s = delay_samples / self.sample_rate
            correlation_strength = np.abs(correlation[max_corr_index])
            self.gain = sigmoid(correlation_strength)
            print(f"推定遅延(FFT): {delay_s:.3f}s ({delay_samples}サンプル) 相関: {correlation_strength:.3f} ゲイン: {self.gain}")

def sigmoid(correlation_strength, midpoint=0.2, steepness=10):
    sig = 1 - 1 / (1 + np.exp(-steepness * (correlation_strength - midpoint)))
    return sig

def apply_volume_limiter(data, gain):
    sample_count = len(data) // 2
    samples = struct.unpack(f'<{sample_count}h', data)
    limited_samples = [int(sample * gain) for sample in samples]
    limited_samples = [int(sample / 7) for sample in samples]
    return struct.pack(f'<{len(limited_samples)}h', *limited_samples)

def apply_volume_limiter0(audio_data):
    """
    音声データに音量制限を適用する
    
    Args:
        audio_data (bytes): 16bit signed integer形式の音声データ
    
    Returns:
        bytes: 音量制限が適用された音声データ
    """
    MAX_AMPLITUDE = 20000 
    LIMITER_RATIO = 0.8

    if len(audio_data) < 2:
        return audio_data
    
    # バイトデータを16bit signed integerの配列に変換
    sample_count = len(audio_data) // 2
    samples = struct.unpack(f'<{sample_count}h', audio_data)
    
    # 音量制限を適用
    limited_samples = []
    for sample in samples:
        # 絶対値が最大振幅を超えている場合は制限
        if abs(sample) > MAX_AMPLITUDE:
            # ソフトリミッティング（急激な変化を避ける）
            if sample > 0:
                limited_sample = int(MAX_AMPLITUDE + (sample - MAX_AMPLITUDE) * LIMITER_RATIO)
                limited_sample = min(limited_sample, 32767)  # 16bit上限
            else:
                limited_sample = int(-MAX_AMPLITUDE + (sample + MAX_AMPLITUDE) * LIMITER_RATIO)
                limited_sample = max(limited_sample, -32768)  # 16bit下限
        else:
            limited_sample = sample
        
        limited_samples.append(limited_sample)
    
    # 16bit signed integerの配列をバイトデータに変換
    return struct.pack(f'<{len(limited_samples)}h', *limited_samples)


# グローバルなエコーキャンセラーインスタンス
echo_canceller = EchoCanceller()

def send_audio(sock):
    """マイクから音声を録音し、ソケット経由で送信する"""
    rec_process = subprocess.Popen(['rec'] + AUDIO_FORMAT, stdout=subprocess.PIPE)
    print("音声送信スレッドを開始しました。")

    try:
        while True:
            data = rec_process.stdout.read(BUFFER_SIZE)
            if not data:
                break

            # エコーキャンセラに送信音声を記録
            echo_canceller.add_sent_audio(data)
            gain = echo_canceller.gain

            #簡易なエコーキャンセラの実装
            data = apply_volume_limiter(data, gain)

            sock.sendall(data)
    except (BrokenPipeError, ConnectionResetError):
        print("送信中に接続が切れました。")
    except Exception as e:
        print(f"send_audioでエラーが発生しました: {e}")
    finally:
        rec_process.terminate()
        print("送信スレッド終了")

def recv_audio(sock, amplitudes, timestamps, duration=60.0):
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

            processed_data = echo_canceller.process_received_audio(data)
            # RMS振幅を記録
            rms = audioop.rms(processed_data, 2)
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
    
    avg_amplitude = sum(amplitudes) / len(amplitudes)
    print(f"平均RMS振幅: {avg_amplitude:.2f}")
    
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

#amplitude_recodeのプロットの謎を理解
if __name__ == '__main__':
    main()