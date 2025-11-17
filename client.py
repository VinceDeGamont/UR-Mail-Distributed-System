import asyncio
import json
import aioconsole
import argparse
import sys
from datetime import datetime

username = ""
my_inbox = [] # format: [{'from': 'A', 'subject': 'Hi', 'msg': '...', 'read': False}, ...]

async def receive_messages(reader):
    """Selalu mendengarkan pesan masuk."""
    while True:
        try:
            data = await reader.read(2048)
            if not data:
                print("\n[!] Disconnected."); sys.exit()
            resp = json.loads(data.decode())
            
            if resp['cmd'] == "INBOX":
                inbox_data = {
                    'from': resp.get('from'),
                    'subject': resp.get('subject', '(No Subject)'),
                    'msg': resp.get('msg'),
                    'cc': resp.get('to_list', []),
                    'read': False # <-- Pesan baru selalu UNREAD
                }
                my_inbox.append(inbox_data)
                
                print(f"\n🔔 [PESAN BARU] Dari: {inbox_data['from']} | Subject: {inbox_data['subject']}\nCmd >> ", end="", flush=True)
                
            elif resp['cmd'] == "INFO":
                print(f"\n[SERVER]: {resp['msg']}")
        except: break

async def user_interface(writer):
    """Menangani input dan menu user."""
    global username
    username = await aioconsole.ainput("Username: ")
    writer.write(json.dumps({"cmd": "LOGIN", "username": username}).encode())
    await writer.drain()

    while True:
        # --- MENU DI-UPDATE (DIGABUNG & RENUMBER) ---
        print("\n===== WELCOME TO UR-MAIL ===== ")
        print("\n=== MENU UTAMA === ")
        print("[1] Kirim Pesan (Batch)")
        print("[2] Inbox & Baca Pesan")    # <-- DIGABUNG
        print("[3] Balas Pesan (Reply)")   # <-- RENUMBER
        print("[4] Forward Pesan")         # <-- RENUMBER
        print("[5] Export Inbox ke TXT")   # <-- RENUMBER
        print("[6] Exit")                  # <-- RENUMBER
        
        choice = await aioconsole.ainput("Pilih Menu >> ")
        
        # --- [1] KIRIM PESAN ---
        if choice == '1':
            # ... (LOGIKA INI TETAP SAMA, TIDAK DIUBAH) ...
            send_queue = []
            print("\n--- Setup Penerima & Pesan ---")
            try:
                count_str = await aioconsole.ainput("Berapa orang yang ingin dikirim? : ")
                count = int(count_str)
                for i in range(count):
                    print(f"\n--- Target ke-{i+1} ---")
                    t_name = await aioconsole.ainput(f"Nama Penerima: ")
                    t_subject = await aioconsole.ainput(f"Subject untuk {t_name}: ")
                    t_msg = await aioconsole.ainput(f"Pesan untuk {t_name}: ")
                    send_queue.append({
                        "to": t_name.strip(), "subject": t_subject, "msg": t_msg, "delay": 0
                    })
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

        # --- [2] LIHAT INBOX & BACA PESAN (DIGABUNG) ---
        elif choice == '2':
            print(f"\n=== INBOX {username} ===")
            if not my_inbox:
                print("(Inbox Kosong)")
                continue # Langsung kembali ke menu utama jika kosong
                
            # 1. Tampilkan daftar inbox
            for i, m in enumerate(my_inbox): 
                status = "[UNREAD]" if not m['read'] else "[ READ ]"
                print(f"{i+1}. {status} | Dari: {m['from']} | Subject: {m['subject']}")
            
            print("---------------------------------")
            
            # 2. Langsung tawarkan untuk membaca
            try:
                idx_str = await aioconsole.ainput("Masukkan nomor pesan yang ingin dibuka (0=Kembali): ")
                idx = int(idx_str) - 1 # (user input 1, artinya index 0)
                
                if idx == -1: # User pilih 0 (Kembali)
                    continue
                
                if 0 <= idx < len(my_inbox):
                    mail = my_inbox[idx]
                    mail['read'] = True # <-- Langsung tandai sudah dibaca
                    
                    # Tampilkan isi pesan
                    print("\n--- [Membaca Pesan] ---")
                    print(f"Dari    : {mail['from']}")
                    print(f"Subject : {mail['subject']}")
                    print("-------------------------")
                    print(f"Pesan   : {mail['msg']}")
                    print("-------------------------")
                    await aioconsole.ainput("Tekan Enter untuk kembali ke menu...")
                else:
                    print("Nomor pesan tidak valid.")
                    
            except ValueError:
                print("Input harus angka.")

        # --- [3] BALAS PESAN (REPLY) (RENUMBER) ---
        elif choice == '3':
            print(f"\n--- Balas Pesan ---")
            if not my_inbox: print("Inbox kosong."); continue
            
            # Tampilkan inbox dulu
            for i, m in enumerate(my_inbox):
                status = "[UNREAD]" if not m['read'] else "[ READ ]"
                print(f"{i+1}. {status} | Dari: {m['from']} | Subject: {m['subject']}")
            
            try:
                idx_str = await aioconsole.ainput("Balas pesan nomor berapa? (0=Batal): ")
                idx = int(idx_str) - 1
                if idx == -1: continue
                
                if 0 <= idx < len(my_inbox):
                    original_mail = my_inbox[idx]
                    target_name = original_mail['from']
                    
                    print(f"Membalas ke: {target_name}")
                    t_subject = f"Re: {original_mail['subject']}"
                    print(f"Subject (Otomatis): {t_subject}")
                    t_msg = await aioconsole.ainput(f"Pesan balasan: ")
                    
                    send_queue = [{"to": target_name, "subject": t_subject, "msg": t_msg, "delay": 0}]
                    writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
                    await writer.drain()
                    print("Balasan terkirim.")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [4] FORWARD PESAN (RENUMBER) ---
        elif choice == '4':
            print(f"\n--- Forward Pesan ---")
            if not my_inbox: print("Inbox kosong."); continue

            for i, m in enumerate(my_inbox):
                status = "[UNREAD]" if not m['read'] else "[ READ ]"
                print(f"{i+1}. {status} | Dari: {m['from']} | Subject: {m['subject']}")
            
            try:
                idx_str = await aioconsole.ainput("Forward pesan nomor berapa? (0=Batal): ")
                idx = int(idx_str) - 1
                if idx == -1: continue

                if 0 <= idx < len(my_inbox):
                    original_mail = my_inbox[idx]
                    fwd_subject = f"Fwd: {original_mail['subject']}"
                    fwd_msg_body = (
                        f"\n--- Pesan Asli ---\n"
                        f"Dari: {original_mail['from']}\n"
                        f"Pesan: {original_mail['msg']}\n"
                        f"------------------"
                    )
                    
                    print(f"Subject (Otomatis): {fwd_subject}")
                    
                    send_queue = []
                    count_str = await aioconsole.ainput("Berapa orang yang ingin dikirim? : ")
                    count = int(count_str)
                    
                    for i in range(count):
                        t_name = await aioconsole.ainput(f"Forward ke (Target {i+1}): ")
                        send_queue.append({
                            "to": t_name.strip(), "subject": fwd_subject, "msg": fwd_msg_body, "delay": 0
                        })
                    
                    print("\n[1] Kirim Langsung [2] Custom Schedule")
                    mode = await aioconsole.ainput("Pilihan Mode: ")
                    if mode == '2':
                        for item in send_queue:
                            d_str = await aioconsole.ainput(f"Delay ke '{item['to']}' (detik): ")
                            try:
                                item['delay'] = int(d_str)
                            except ValueError: item['delay'] = 0
                    
                    writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
                    await writer.drain()
                    print("Pesan di-forward...")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [5] EXPORT MAILBOX (RENUMBER) ---
        elif choice == '5':
            print(f"\n--- Mengekspor Mailbox {username} ---")
            if not my_inbox:
                print("Inbox kosong."); continue
            
            filename = f"{username}_mailbox_export.txt"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"=== Arsip Mailbox untuk {username} ===\n")
                    f.write(f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    for i, mail in enumerate(my_inbox):
                        f.write(f"--- Pesan #{i+1} ---\n")
                        f.write(f"Status: {'UNREAD' if not mail['read'] else 'READ'}\n")
                        f.write(f"Dari: {mail.get('from', 'Unknown')}\n")
                        f.write(f"Subject: {mail.get('subject', 'N/A')}\n")
                        f.write(f"Pesan: {mail.get('msg', '(Kosong)')}\n")
                        f.write("---------------------\n\n")
                
                print(f"✅ Berhasil! Inbox diekspor ke: {filename}")
                
            except Exception as e:
                print(f"❌ Gagal mengekspor file: {e}")

        # --- [6] EXIT (RENUMBER) ---
        elif choice == '6': 
            print("Keluar dari UR-Mail..."); sys.exit()

# --- (async def main dan if __name__ == '__main__' tetap sama) ---
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