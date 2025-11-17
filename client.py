import asyncio
import json
import aioconsole
import argparse
import sys
from datetime import datetime

username = ""
my_inbox = []

async def receive_messages(reader):
    while True:
        try:
            data = await reader.read(2048)
            if not data:
                print("\n[!] Disconnected."); sys.exit()
            resp = json.loads(data.decode())
            
            if resp['cmd'] == "INBOX":
                
                inbox_data = {
                    'from': resp.get('from'),
                    'msg': resp.get('msg'),
                    'cc': resp.get('to_list', []) 
                }
                
                my_inbox.append(inbox_data)
                
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
        print("\n===== WELCOME TO (UR-Mail) =====")
        print("<<-- MENU UTAMA -->>")
        print("[1] Kirim Pesan (Batch)")
        print("[2] Lihat Inbox")
        print("[3] Balas Pesan (Reply)")
        print("[4] Export Inbox ke TXT")
        print("[5] Exit")
        
        choice = await aioconsole.ainput("Pilih Menu >> ")
        
        # --- [1] KIRIM PESAN ---
        if choice == '1':
            send_queue = []
            print("\n--- Setup Penerima & Pesan ---")
            try:
                count_str = await aioconsole.ainput("Berapa orang yang ingin dikirim? : ")
                count = int(count_str)
                for i in range(count):
                    print(f"\n--- Target ke-{i+1} ---")
                    t_name = await aioconsole.ainput(f"Nama Penerima: ")
                    t_msg = await aioconsole.ainput(f"Pesan untuk {t_name}: ")
                    send_queue.append({"to": t_name.strip(), "msg": t_msg, "delay": 0})
            except ValueError:
                print("Input jumlah harus angka!"); continue
            
            print("\n--- Metode Pengiriman ---")
            print("[1] Kirim Langsung (Instant)")
            print("[2] Custom Schedule (Delay per orang)")
            mode = await aioconsole.ainput("Pilihan Mode: ")
            
            if mode == '2':
                for item in send_queue:
                    try:
                        d_str = await aioconsole.ainput(f"Delay ke '{item['to']}' (detik): ")
                        item['delay'] = int(d_str)
                    except ValueError: item['delay'] = 0
            
            writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
            await writer.drain()
            print(f"Permintaan batch dikirim...")

        # --- [2] LIHAT INBOX ---
        elif choice == '2':
            print(f"\n=== INBOX {username} ===")
            if not my_inbox: print("(Kosong)")
            for i, m in enumerate(my_inbox): 
                print(f"{i+1}. Dari: {m['from']} | Pesan: {m['msg']}")

        # --- [3] BALAS PESAN ---
        elif choice == '3':
            if not my_inbox:
                print("Inbox kosong. Tidak ada yang bisa dibalas."); continue
            
            valid_targets = set()
            for mail in my_inbox:
                valid_targets.add(mail['from'])
                for person in mail.get('cc', []):
                    if person != username: valid_targets.add(person)
            
            valid_list = list(valid_targets)
            print("\n--- Fitur Balas Pesan ---")
            print(f"Bisa membalas ke: {', '.join(valid_list)}")
            
            send_queue = []
            try:
                count_str = await aioconsole.ainput("Berapa orang yang ingin dibalas? : ")
                count = int(count_str)
                
                for i in range(count):
                    t_name_raw = await aioconsole.ainput(f"Nama Penerima ke-{i+1}: ")
                    t_name = t_name_raw.strip()
                    
                    if t_name not in valid_list:
                        print(f"Error: '{t_name}' tidak valid. Diskip."); continue

                    t_msg = await aioconsole.ainput(f"Pesan balasan untuk {t_name}: ")
                    
                    send_queue.append({"to": t_name, "msg": t_msg, "delay": 0})
                    
            except ValueError:
                print("Input jumlah harus angka!"); continue
            
            if not send_queue:
                print("Tidak ada balasan valid."); continue

            print("\n[1] Kirim Langsung")
            print("[2] Custom Schedule")

            mode = await aioconsole.ainput("Pilihan Mode: ")
            
            if mode == '2':
                for item in send_queue:
                    try:
                        d_str = await aioconsole.ainput(f"Delay balasan ke '{item['to']}' (detik): ")
                        item['delay'] = int(d_str)
                    except ValueError: item['delay'] = 0
            
            writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
            await writer.drain()
            print(f"Permintaan balasan dikirim...")

        # --- [4] EXPORT MAILBOX ---
        elif choice == '4':
            print(f"\n--- Mengekspor Mailbox {username} ---")
            if not my_inbox:
                print("Inbox kosong. Tidak ada yang diekspor.")
                continue
            
            filename = f"{username}_mailbox_export.txt"
            try:
                # Mode 'w' (write) akan menimpa file lama jika ada (full export)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"=== Arsip Mailbox untuk {username} ===\n")
                    f.write(f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=======================================\n\n")
                    
                    # Loop semua pesan di memori (my_inbox)
                    for i, mail in enumerate(my_inbox):
                        sender = mail.get('from', 'Unknown')
                        message = mail.get('msg', '(Pesan kosong)')
                        f.write(f"--- Pesan #{i+1} ---\n")
                        f.write(f"Dari: {sender}\n")
                        f.write(f"Pesan: {message}\n")
                        f.write("----------------------\n\n")
                
                print(f"✅ Berhasil! Inbox telah diekspor ke file: {filename}")
                
            except Exception as e:
                print(f"❌ Gagal mengekspor file: {e}")

        # --- [5] EXIT ---
        elif choice == '5': 
            print("Keluar dari UR-Mail...")
            sys.exit()

# ... (Sisa kode: async def main dan if __name__ == '__main__' tetap sama) ...
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