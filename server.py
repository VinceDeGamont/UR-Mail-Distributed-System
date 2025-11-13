import asyncio
import json
import argparse
import sys

connected_users = {}

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    current_user = None

    try:
        while True:
            data = await reader.read(2048)
            if not data: break
            
            try:
                request = json.loads(data.decode())
            except json.JSONDecodeError: continue

            command = request.get('cmd')

            if command == 'LOGIN':
                username = request.get('username')
                connected_users[username] = writer
                current_user = username
                print(f"[+] {username} logged in from {addr}")
                writer.write(json.dumps({"cmd": "INFO", "msg": f"Welcome {username}"}).encode())
                await writer.drain()

            # --- LOGIC BARU: SEND_BATCH (Pesan Beda-Beda) ---
            elif command == 'SEND_BATCH':
                queue = request.get('queue') # List of {"to": "A", "msg": "Hai", "delay": 2}
                
                print(f"[*] {current_user} memulai pengiriman batch...")

                for item in queue:
                    target_name = item['to']
                    delay = item['delay']
                    specific_msg = item['msg'] # <--- Ambil pesan UNIK per target
                    
                    # 1. Visual Countdown & Delay
                    if delay > 0:
                        # Info ke Pengirim
                        writer.write(json.dumps({
                            "cmd": "INFO", 
                            "msg": f"Server menunda {delay} detik untuk pesan ke {target_name}..."
                        }).encode())
                        await writer.drain()

                        # Animasi Terminal Server
                        print(f"   ➡️  Target: {target_name} | Delay: {delay}s")
                        for remaining in range(delay, 0, -1):
                            sys.stdout.write(f"\r      ⏳ Mengirim dalam: {remaining} detik... ")
                            sys.stdout.flush()
                            await asyncio.sleep(1)
                        
                        sys.stdout.write(f"\r      🚀 Mengirim ke {target_name}!          \n")
                        sys.stdout.flush()
                    
                    # 2. Proses Kirim Pesan
                    if target_name in connected_users:
                        packet = {
                            "cmd": "INBOX",
                            "from": current_user,
                            "to_list": [target_name], # Karena pesan beda, ini privat (bukan group chat)
                            "msg": specific_msg
                        }
                        try:
                            target_writer = connected_users[target_name]
                            target_writer.write(json.dumps(packet).encode())
                            await target_writer.drain()
                            print(f"      ✅ Terkirim: '{specific_msg}' ke {target_name}")
                        except:
                            print(f"      ❌ Gagal kirim ke {target_name}")
                    else:
                        print(f"      ⚠️  {target_name} Offline")

                # Konfirmasi Selesai
                writer.write(json.dumps({"cmd": "INFO", "msg": "✅ Semua pesan batch selesai."}).encode())
                await writer.drain()

    except Exception: pass
    finally:
        if current_user in connected_users: del connected_users[current_user]
        writer.close()

async def main(host, port):
    server = await asyncio.start_server(handle_client, host, port)
    print(f"=== SERVER BERJALAN PADA {host}:{port} ===")
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="UR-Mail Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='IP Address')
    parser.add_argument('--port', type=int, default=8888, help='Port')
    args = parser.parse_args()

    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main(args.host, args.port)) 
    except KeyboardInterrupt:
        print("\nServer Stopped.")