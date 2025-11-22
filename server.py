import asyncio
import json
import argparse
import sys

# === STATE SERVER ===
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
            except json.JSONDecodeError:
                print(f"[ERR] Menerima data JSON tidak valid dari {addr}")
                continue

            command = request.get('cmd')

            # --- Perintah LOGIN ---
            if command == 'LOGIN':
                username = request.get('username')
                connected_users[username] = writer
                current_user = username
                print(f"[+] {username} login dari {addr}")
                
                writer.write(json.dumps({"cmd": "INFO", "msg": f"Welcome {username}"}).encode())
                await writer.drain()

            # --- Perintah SEND_BATCH ---
            elif command == 'SEND_BATCH':
                queue = request.get('queue') 
                print(f"[*] {current_user} memulai pengiriman batch...")

                for item in queue:
                    target_name = item['to']
                    delay = item['delay']
                    specific_msg = item['msg']
                    specific_subject = item.get('subject', '(No Subject)')
                    
                    # Fitur Delay
                    if delay > 0:
                        writer.write(json.dumps({
                            "cmd": "INFO", 
                            "msg": f"Server menunda {delay} detik untuk pesan ke {target_name}..."
                        }).encode())
                        await writer.drain()

                        print(f"   -> Target: {target_name} | Delay: {delay}s")
                        for remaining in range(delay, 0, -1):
                            sys.stdout.write(f"\r      [WAIT] Mengirim dalam: {remaining} detik... ")
                            sys.stdout.flush()
                            await asyncio.sleep(1)
                        
                        sys.stdout.write(f"\r      [SEND] Mengirim ke {target_name}!                \n")
                        sys.stdout.flush()
                    
                    # Pengiriman Pesan
                    if target_name in connected_users:
                        packet = {
                            "cmd": "INBOX",
                            "from": current_user,
                            "to_list": [target_name], 
                            "subject": specific_subject,
                            "msg": specific_msg
                        }
                        target_writer = connected_users[target_name]
                        try:
                            target_writer.write(json.dumps(packet).encode())
                            await target_writer.drain()
                            print(f"      [OK] Terkirim: (Subj: {specific_subject}) ke {target_name}")
                        except Exception as e:
                            print(f"      [ERR] Gagal kirim ke {target_name}: {e}")
                    else:
                        print(f"      [WARN] {target_name} Offline")

                writer.write(json.dumps({"cmd": "INFO", "msg": "[OK] Semua pesan batch selesai."}).encode())
                await writer.drain()

    except Exception as e:
        print(f"[ERR] Koneksi {addr} error: {e}")
        pass
    finally:
        if current_user and current_user in connected_users:
            del connected_users[current_user]
            print(f"[-] {current_user} disconnected.")
        writer.close()

async def main(host, port):
    server = await asyncio.start_server(handle_client, host, port)
    print(f"=== SERVER UR-MAIL BERJALAN PADA {host}:{port} ===")
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="UR-Mail Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='IP Address (0.0.0.0 = semua)')
    parser.add_argument('--port', type=int, default=8888, help='Port')
    args = parser.parse_args()

    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main(args.host, args.port)) 
    except KeyboardInterrupt:
        print("\nServer dimatikan.")