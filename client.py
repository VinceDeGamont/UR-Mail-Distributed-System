import asyncio
import json
import aioconsole
import argparse
import sys
from datetime import datetime

# === STATE CLIENT ===
username = ""
my_inbox = [] 
my_outbox = [] 

async def receive_messages(reader):
    """Selalu mendengarkan pesan masuk di background."""
    while True:
        try:
            data = await reader.read(2048)
            if not data:
                print("\n[!] Koneksi ke server terputus."); sys.exit()
                break

            resp = json.loads(data.decode())
            
            if resp['cmd'] == "INBOX":
                inbox_data = {
                    'from': resp.get('from'),
                    'subject': resp.get('subject', '(No Subject)'),
                    'msg': resp.get('msg'),
                    'cc': resp.get('to_list', []),
                    'read': False 
                }
                my_inbox.append(inbox_data)
                
                # [UBAH] Mengganti 🔔 dengan '[NEW MSG]'
                print(f"\n[NEW MSG] Dari: {inbox_data['from']} | Subject: {inbox_data['subject']}\nCmd >> ", end="", flush=True)
            
            elif resp['cmd'] == "INFO":
                print(f"\n[SERVER]: {resp['msg']}\nCmd >> ", end="", flush=True)
                
        except Exception as e:
            # [UBAH]
            print(f"\n[ERR] Gagal membaca data dari server: {e}")
            sys.exit()
            break

async def user_interface(writer):
    """Menangani input dan menu user di foreground."""
    global username
    
    username = await aioconsole.ainput("Masukkan Username: ")
    writer.write(json.dumps({"cmd": "LOGIN", "username": username}).encode())
    await writer.drain()

    while True:
        print("\n===== WELCOME TO UR-MAIL ===== ")
        print(f"\n=== MENU UTAMA (User: {username}) ===")
        print("[1] Kirim Pesan (Batch)")
        print("[2] Inbox & Baca Pesan")
        print("[3] Lihat Pesan Terkirim (Outbox)")
        print("[4] Balas Pesan (Reply)")
        print("[5] Forward Pesan")
        print("[6] Hapus Pesan")
        print("[7] Export Mailbox ke TXT")
        print("[8] Exit")
        
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
            
            for item in send_queue:
                my_outbox.append(item)
            print(f"Permintaan batch dikirim...")

        # --- [2] LIHAT INBOX & BACA PESAN ---
        elif choice == '2':
            print(f"\n=== INBOX {username} ===")
            if not my_inbox:
                print("(Inbox Kosong)"); continue 
            
            # [UBAH] Indikator teks sederhana
            for i, m in enumerate(my_inbox): 
                status = "[UNREAD]" if not m['read'] else "[ READ ]"
                print(f"{i+1}. {status} | Dari: {m['from']} | Subject: {m['subject']}")
            print("---------------------------------------")
            
            try:
                idx_str = await aioconsole.ainput("Masukkan nomor pesan yang ingin dibuka (0=Kembali): ")
                idx = int(idx_str) - 1 
                
                if idx == -1: continue
                
                if 0 <= idx < len(my_inbox):
                    mail = my_inbox[idx]
                    mail['read'] = True 
                    
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

        # --- [3] LIHAT PESAN TERKIRIM (OUTBOX) ---
        elif choice == '3':
            print(f"\n=== OUTBOX {username} (Pesan Terkirim) ===")
            if not my_outbox:
                print("(Outbox Kosong)"); continue
            
            for i, m in enumerate(my_outbox):
                print(f"{i+1}. Ke: {m['to']} | Subject: {m['subject']} | Delay: {m['delay']}s")
                print(f"   Pesan: {m['msg']}\n")
            
            print("------------------------------------")
            await aioconsole.ainput("Tekan Enter untuk kembali ke menu...")

        # --- [4] BALAS PESAN (REPLY) ---
        elif choice == '4':
            print(f"\n--- Balas Pesan ---")
            if not my_inbox: print("Inbox kosong."); continue
            
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
                    
                    my_outbox.append(send_queue[0])
                    print("Balasan terkirim.")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [5] FORWARD PESAN ---
        elif choice == '5':
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
                    
                    print("\n[1] Kirim Langsung (Instant)")
                    print("[2] Custom Schedule (Delay per orang)\n")
                    mode = await aioconsole.ainput("Pilihan Mode: ")
                    if mode == '2':
                        for item in send_queue:
                            d_str = await aioconsole.ainput(f"Delay ke '{item['to']}' (detik): ")
                            try: item['delay'] = int(d_str)
                            except ValueError: item['delay'] = 0
                    
                    writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
                    await writer.drain()
                    
                    for item in send_queue:
                        my_outbox.append(item)
                    print("Pesan di-forward...")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [6] HAPUS PESAN ---
        elif choice == '6':
            print(f"\n--- Hapus Pesan dari Inbox ---")
            if not my_inbox:
                print("Inbox kosong."); continue
            
            for i, m in enumerate(my_inbox): 
                status = "[UNREAD]" if not m['read'] else "[ READ ]"
                print(f"{i+1}. {status} | Dari: {m['from']} | Subject: {m['subject']}")
            
            try:
                idx_str = await aioconsole.ainput("Masukkan nomor pesan yang ingin dihapus (0=Batal): ")
                idx = int(idx_str) - 1
                
                if idx == -1: continue
                
                if 0 <= idx < len(my_inbox):
                    deleted_mail = my_inbox.pop(idx)
                    print(f"Pesan '{deleted_mail['subject']}' telah dihapus.")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [7] EXPORT MAILBOX ---
        elif choice == '7':
            print(f"\n--- Mengekspor Mailbox {username} ---")
            if not my_inbox and not my_outbox:
                print("Inbox dan Outbox kosong."); continue
            
            filename = f"{username}_mailbox_export.txt"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"=== Arsip Mailbox untuk {username} ===\n")
                    f.write(f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    f.write("========== INBOX ==========\n")
                    if not my_inbox: f.write("(Inbox Kosong)\n\n")
                    else:
                        for i, mail in enumerate(my_inbox):
                            f.write(f"--- Pesan #{i+1} ---\n")
                            f.write(f"Status: {'UNREAD' if not mail['read'] else 'READ'}\n")
                            f.write(f"Dari: {mail.get('from', 'Unknown')}\n")
                            f.write(f"Subject: {mail.get('subject', 'N/A')}\n")
                            f.write(f"Pesan: {mail.get('msg', '(Kosong)')}\n")
                            f.write("---------------------\n\n")

                    f.write("========= OUTBOX ==========\n")
                    if not my_outbox: f.write("(Outbox Kosong)\n\n")
                    else:
                        for i, m in enumerate(my_outbox):
                            f.write(f"--- Pesan Terkirim #{i+1} ---\n")
                            f.write(f"Ke: {m['to']}\n")
                            f.write(f"Subject: {m['subject']}\n")
                            f.write(f"Delay: {m['delay']}s\n")
                            f.write(f"Pesan: {m['msg']}\n")
                            f.write("---------------------\n\n")
                
                print(f"[OK] Berhasil! Mailbox diekspor ke: {filename}")
            except Exception as e:
                print(f"[ERR] Gagal mengekspor file: {e}")

        # --- [8] EXIT ---
        elif choice == '8': 
            print("Keluar dari UR-Mail..."); sys.exit()


async def main(host, port):
    print(f"Menghubungkan ke Server {host}:{port} ...")
    try:
        reader, writer = await asyncio.open_connection(host, port)
        print("[OK] Connected!")
        await asyncio.gather(receive_messages(reader), user_interface(writer))
    except Exception as e:
        print(f"[ERR] Gagal Connect: {e}")

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