import asyncio  
import json
import argparse 
import sys      

# === STATE SERVER ===
# dictionary untuk menyimpan user yg sedang online
# format: {'username': writer_object} -> 'writer' adalah koneksi ke user tsb
connected_users = {}

async def handle_client(reader, writer):
    """
    function (coroutine) yg dijalankan setiap kali ada client baru terkoneksi
    tugasnya: menerima pesan dari client tersebut dan memprosesnya
    """
    
    # ambil IP Address dan Port client untuk keperluan log
    addr = writer.get_extra_info('peername')
    current_user = None # variabel untuk menyimpan username client ini setelah login

    try:
        # loop utama: terus mendengarkan pesan dari client selama koneksi aktif
        while True:
            # read data dari client (maksimal 2048 bytes)
            # 'await' berarti server bisa kerjain hal lain sambil nunggu data
            data = await reader.read(2048)
            if not data: break # jika data kosong, artinya client disconnect, keluar loop
            
            try:
                # ubah data bytes menjadi string, lalu di-parse dari JSON ke dictionary Python
                request = json.loads(data.decode())
            except json.JSONDecodeError:
                # jika data bukan JSON yg valid, catat sbg error dan lanjut ke iterasi berikutnya
                print(f"[ERR] Menerima data JSON tidak valid dari {addr}")
                continue

            command = request.get('cmd') # ambil jenis Command dari pesan

            # --- Command LOGIN ---
            if command == 'LOGIN':
                username = request.get('username')
                # simpan koneksi user ke dlm dictionary 'connected_users'
                connected_users[username] = writer
                current_user = username # set user saat ini
                print(f"[+] {username} login dari {addr}")
                
                # kirim pesan sambutan balik ke client
                writer.write(json.dumps({"cmd": "INFO", "msg": f"Welcome {username}"}).encode())
                await writer.drain() # pastikan data benar benar terkirim

            # --- Command SEND_BATCH (Kirim Pesan Banyak) ---
            elif command == 'SEND_BATCH':
                queue = request.get('queue') # ambil queue pesan
                print(f"[*] {current_user} memulai pengiriman batch...")

                # loop melalui setiap pesan dlm queue
                for item in queue:
                    target_name = item['to']
                    delay = item['delay']
                    specific_msg = item['msg']
                    specific_subject = item.get('subject', '(No Subject)')
                    
                    # fitur delay: jika ada delay, tunggu dulu
                    if delay > 0:
                        # beri tahu pengirim bahwa pesan sedang ditunda
                        writer.write(json.dumps({
                            "cmd": "INFO", 
                            "msg": f"Server menunda {delay} detik untuk pesan ke {target_name}..."
                        }).encode())
                        await writer.drain()

                        print(f"   -> Target: {target_name} | Delay: {delay}s")
                        # loop countdown di terminal server
                        for remaining in range(delay, 0, -1):
                            sys.stdout.write(f"\r      [WAIT] Mengirim dlm: {remaining} detik... ")
                            sys.stdout.flush() # untuk paksa tampilkan teks di terminal, hehe
                            # server 'tidur' 1 detik. 'await' memastikan ini tidak memblokir client lain
                            await asyncio.sleep(1)
                        
                        sys.stdout.write(f"\r      [SEND] Mengirim ke {target_name}!                \n")
                        sys.stdout.flush()
                    
                    # proses pengiriman pesan: cek apakah penerima online
                    if target_name in connected_users:
                        # buat packet pesan untuk penerima
                        packet = {
                            "cmd": "INBOX",
                            "from": current_user,
                            "to_list": [target_name], 
                            "subject": specific_subject,
                            "msg": specific_msg
                        }
                        # ambil koneksi (writer) milik si target
                        target_writer = connected_users[target_name]
                        try:
                            # kirim paket pesan ke target
                            target_writer.write(json.dumps(packet).encode())
                            await target_writer.drain()
                            print(f"      [OK] Terkirim: (Subj: {specific_subject}) ke {target_name}")
                        except Exception as e:
                            print(f"      [ERR] Gagal kirim ke {target_name}: {e}")
                    else:
                        # jika target tidak ada di 'connected_users', berarti offline
                        print(f"      [WARN] {target_name} Offline")

                # setelah semua pesan dlm batch diproses, beri tahu pengirim
                writer.write(json.dumps({"cmd": "INFO", "msg": "[OK] Semua pesan batch selesai."}).encode())
                await writer.drain()

    except Exception as e:
        print(f"[ERR] Koneksi {addr} error: {e}")
        pass # lanjut ke bagian 'finally'
    finally:
        # ini bagian yg SELALU dijalankan saat koneksi ditutup (baik normal maupun error)
        # ini berguna untuk bersih bersih memory
        if current_user and current_user in connected_users:
            # hapus user dari daftar online
            del connected_users[current_user]
            print(f"[-] {current_user} disconnected.")
        writer.close() # tutup connection 

async def main(host, port):
    """ Coroutine utama untuk menjalankan server """
    # start asyncio server pada host dan port yg ditentukan
    # setiap ada koneksi masuk, fungsi 'handle_client' akan dipanggil
    server = await asyncio.start_server(handle_client, host, port)
    print(f"=== SERVER UR-MAIL BERJALAN PADA {host}:{port} ===")
    # menjaga server tetap berjalan selamanya untuk menerima koneksi
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    # setup argumen command line untuk IP dan Port
    parser = argparse.ArgumentParser(description="UR-Mail Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='IP Address (0.0.0.0 = semua)')
    parser.add_argument('--port', type=int, default=8888, help='Port')
    args = parser.parse_args()

    try:
        # konfigurasi khusus untuk Windows agar asyncio berjalan lancar
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # menjalankan coroutine utama 'main' dlm event loop asyncio
        asyncio.run(main(args.host, args.port)) 
    except KeyboardInterrupt:
        # menangkap interrupt Ctrl+C agar server berhenti dengan rapi
        print("\nServer dimatikan.")