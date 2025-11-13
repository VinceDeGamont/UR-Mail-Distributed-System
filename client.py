import asyncio
import json
import aioconsole
import argparse
import sys
from datetime import datetime

username = ""
my_inbox = []

def save_to_file(sender, msg, timestamp):
    with open(f"{username}_mailbox.txt", "a") as f:
        f.write(f"[{timestamp}] {sender}: {msg}\n")

async def receive_messages(reader):
    while True:
        try:
            data = await reader.read(2048)
            if not data:
                print("\n[!] Disconnected."); sys.exit()
            resp = json.loads(data.decode())
            if resp['cmd'] == "INBOX":
                my_inbox.append(resp)
                save_to_file(resp['from'], resp['msg'], datetime.now().strftime("%H:%M"))
                print(f"\n🔔 [BARU] {resp['from']}: {resp['msg']}\nCmd >> ", end="", flush=True)
            elif resp['cmd'] == "INFO":
                print(f"\n[SERVER]: {resp['msg']}")
        except: break

async def user_interface(writer):
    global username
    username = await aioconsole.ainput("Username: ")
    writer.write(json.dumps({"cmd": "LOGIN", "username": username}).encode())
    await writer.drain()

    while True:
        print("\n=== MENU UTAMA ===")
        print("[1] Kirim Pesan (Batch / Multi-Target)")
        print("[2] Inbox")
        print("[3] Reply")
        print("[4] Exit")
        
        choice = await aioconsole.ainput("Pilih Menu >> ")
        
        if choice == '1':
            send_queue = [] # Menampung list target dan pesan uniknya
            
            print("\n--- Setup Penerima & Pesan ---")
            try:
                count_str = await aioconsole.ainput("Berapa orang yang ingin dikirim? : ")
                count = int(count_str)
                
                # LOOP INPUT NAMA DAN PESAN BERBEDA
                for i in range(count):
                    print(f"\n--- Target ke-{i+1} ---")
                    t_name = await aioconsole.ainput(f"Nama Penerima: ")
                    t_msg = await aioconsole.ainput(f"Pesan untuk {t_name}: ")
                    
                    # Simpan sementara dengan default delay 0
                    send_queue.append({
                        "to": t_name.strip(),
                        "msg": t_msg,
                        "delay": 0
                    })
            except ValueError:
                print("Input jumlah harus angka!")
                continue

            # PILIH MODE PENGIRIMAN
            print("\n--- Metode Pengiriman ---")
            print("[1] Kirim Langsung (Instant)")
            print("[2] Custom Schedule (Atur delay per orang)")
            mode = await aioconsole.ainput("Pilihan Mode: ")
            
            if mode == '2':
                print("\n--- Konfigurasi Waktu ---")
                # Loop ulang queue yang sudah dibuat untuk update delay-nya
                for item in send_queue:
                    target_name = item['to']
                    try:
                        d_str = await aioconsole.ainput(f"Delay pengiriman ke '{target_name}' (detik): ")
                        item['delay'] = int(d_str)
                    except ValueError:
                        item['delay'] = 0
            
            # Payload dikirim ke server
            # Perhatikan: 'msg' sekarang ada di dalam setiap item di 'queue', bukan di luar.
            payload = {
                "cmd": "SEND_BATCH", 
                "queue": send_queue
            }
            
            writer.write(json.dumps(payload).encode())
            await writer.drain()
            print(f"Permintaan batch dikirim ke server...")

        elif choice == '2':
            print(f"\n=== INBOX ===")
            for i, m in enumerate(my_inbox): print(f"{i+1}. {m['from']}: {m['msg']}")
            if not my_inbox: print("(Kosong)")
            
        elif choice == '3':
            if my_inbox:
                l = my_inbox[-1]
                m = await aioconsole.ainput(f"Reply {l['from']}: ")
                # Format reply disesuaikan dengan struktur BATCH
                q = [{"to": l['from'], "msg": m, "delay": 0}]
                writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": q}).encode())
                await writer.drain()
            else:
                print("Inbox kosong.")
                
        elif choice == '4': sys.exit()

async def main(host, port):
    print(f"Menghubungkan ke Server {host}:{port} ...")
    try:
        reader, writer = await asyncio.open_connection(host, port)
        print("✅ Connected!")
        await asyncio.gather(receive_messages(reader), user_interface(writer))
    except Exception as e:
        print(f"❌ Gagal Connect: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="UR-Mail Client")
    parser.add_argument('--host', type=str, default='127.0.0.1', help='IP Server Tujuan')
    parser.add_argument('--port', type=int, default=8888, help='Port Server Tujuan')
    args = parser.parse_args()

    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass