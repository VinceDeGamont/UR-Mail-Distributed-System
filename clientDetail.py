import asyncio      # main library
import json         # untuk format data JSON
import aioconsole   # library untuk input di terminal yg non-blocking
import argparse     # untuk argumen command line (IP Server, Port)
import sys          # untuk operasi sistem (keluar program)
from datetime import datetime # untuk mengambil waktu saat export file

# === STATE CLIENT ===
username = ""      # menyimpan username yg sedang login
my_inbox = []      # list untuk simpan pesan masuk (Inbox) di memori
my_outbox = []     # list untuk simpan pesan terkirim (Outbox) di memori

async def receive_messages(reader):
    """
    Coroutine ini berjalan di BACKGROUND (latar belakang).
    Tugasnya HANYA mendengarkan pesan dari server terus-menerus.
    """
    try:
        while True:
            # membaca data dari server
            data = await reader.read(2048)
            if not data:
                # jika data kosong, server menutup koneksi
                print("\n[!] Koneksi ke server terputus.")
                break # keluar loop

            # parse data JSON dari server
            resp = json.loads(data.decode())
            
            # jika server mengirim pesan baru (INBOX)
            if resp['cmd'] == "INBOX":
                # buat struktur data pesan
                inbox_data = {
                    'from': resp.get('from'),
                    'subject': resp.get('subject', '(No Subject)'),
                    'msg': resp.get('msg'),
                    'cc': resp.get('to_list', []),
                    'read': False # status awal 'belum dibaca'
                }
                # simpan ke list 'my_inbox'
                my_inbox.append(inbox_data)
                
                # tampilkan notifikasi real-time di terminal.
                # 'Cmd >>' dicetak lagi agar prompt menu tidak hilang.
                print(f"\n[NEW MSG] Dari: {inbox_data['from']} | Subject: {inbox_data['subject']}\nCmd >> ", end="", flush=True)
            
            # jika server mengirim pesan informasi (INFO)
            elif resp['cmd'] == "INFO":
                print(f"\n[SERVER]: {resp['msg']}\nCmd >> ", end="", flush=True)
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\n[ERR] Gagal membaca data dari server: {e}")
        pass

async def user_interface(writer):
    """
    coroutine ini berjalan di FOREGROUND (depan).
    tugasnya => menampilkan menu dan meminta input dari user.
    """
    global username
    
    # minta input username
    username = await aioconsole.ainput("Masukkan Username: ")
    # kirim command LOGIN ke server
    writer.write(json.dumps({"cmd": "LOGIN", "username": username}).encode())
    await writer.drain()

    # loop menu utama
    while True:
        # ... (Print menu pilihan) ...
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
        
        try:
            # minta input pilihan menu dari user
            choice = await aioconsole.ainput("Pilih Menu >> ")
        except EOFError:
            # error handling jika terminal ditutup paksa
            print("\nInput ditutup. Keluar.")
            break

        # --- [1] KIRIM PESAN (Batch) ---
        if choice == '1':
            send_queue = [] # list untuk menampung antrian pesan yang akan dikirim
            print("\n--- Setup Penerima & Pesan ---")
            try:
                # minta jumlah penerima
                count_str = await aioconsole.ainput("Berapa orang yang ingin dikirim? : ")
                count = int(count_str)
                # loop untuk meminta detail setiap pesan
                for i in range(count):
                    print(f"\n--- Target ke-{i+1} ---")
                    t_name = await aioconsole.ainput(f"Nama Penerima: ")
                    t_subject = await aioconsole.ainput(f"Subject untuk {t_name}: ")
                    t_msg = await aioconsole.ainput(f"Pesan untuk {t_name}: ")
                    # tambahkan pesan ke antrian
                    send_queue.append({
                        "to": t_name.strip(), "subject": t_subject, "msg": t_msg, "delay": 0
                    })
            except ValueError:
                print("Input jumlah harus angka!"); continue
            
            # minta mode pengiriman
            print("\n--- Metode Pengiriman ---")
            print("[1] Kirim Langsung (Instant)")
            print("[2] Custom Schedule (Delay per orang)")
            mode = await aioconsole.ainput("Pilihan Mode: ")
            
            # jika mode schedule, minta input delay untuk tiap pesan
            if mode == '2':
                for item in send_queue:
                    try:
                        d_str = await aioconsole.ainput(f"Delay ke '{item['to']}' (detik): ")
                        item['delay'] = int(d_str)
                    except ValueError: item['delay'] = 0
            
            # kirim seluruh antrian pesan (batch) ke server
            writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
            await writer.drain()
            
            # menyimpan salinan pesan ke 'my_outbox' lokal
            for item in send_queue:
                my_outbox.append(item)
            print(f"Permintaan batch dikirim...")

        # --- [2] LIHAT INBOX & BACA PESAN ---
        elif choice == '2':
            print(f"\n=== INBOX {username} ===")
            if not my_inbox:
                print("(Inbox Kosong)"); continue 
            
            # menampilkan daftar pesan di inbox
            for i, m in enumerate(my_inbox): 
                status = "[UNREAD]" if not m['read'] else "[ READ ]"
                print(f"{i+1}. {status} | Dari: {m['from']} | Subject: {m['subject']}")
            print("---------------------------------------")
            
            try:
                # meminta nomor pesan yang ingin dibaca
                idx_str = await aioconsole.ainput("Masukkan nomor pesan yang ingin dibuka (0=Kembali): ")
                idx = int(idx_str) - 1 # konversi ke index list (mulai dari 0)
                
                if idx == -1: continue # user memilih kembali
                
                if 0 <= idx < len(my_inbox):
                    mail = my_inbox[idx]
                    mail['read'] = True # update status jadi 'sudah dibaca/read'
                    
                    # tampilkan isi pesan lengkap
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
            # (logikanya mirip dengan inbox, tapi yg di tampilkan 'my_outbox')
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
            # (menampilkan inbox, meminta nomor pesan untuk dibalas)
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
                    target_name = original_mail['from'] # target adalah pengirim asli
                    
                    print(f"Membalas ke: {target_name}")
                    t_subject = f"Re: {original_mail['subject']}" # otomatis tambah 'Re:'
                    print(f"Subject (Otomatis): {t_subject}")
                    t_msg = await aioconsole.ainput(f"Pesan balasan: ")
                    
                    # buat queue (berisi 1 pesan balasan)
                    send_queue = [{"to": target_name, "subject": t_subject, "msg": t_msg, "delay": 0}]
                    # kirim ke server
                    writer.write(json.dumps({"cmd": "SEND_BATCH", "queue": send_queue}).encode())
                    await writer.drain()
                    
                    # simpan ke outbox
                    my_outbox.append(send_queue[0])
                    print("Balasan terkirim.")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [5] FORWARD PESAN ---
        elif choice == '5':
            # (mirip reply, tapi subject jadi 'Fwd:' dan meminta target baru)
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
                    fwd_subject = f"Fwd: {original_mail['subject']}" # otomatis tambah 'Fwd:'
                    # format isi pesan yang akan diforward
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
                    print("[2] Custom Schedule (Delay)")
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
            # tampilkan dulu isi inbox, minta nomor pesan untuk dihapus
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
                    # hapus pesan dari list 'my_inbox' berdasarkan index
                    deleted_mail = my_inbox.pop(idx)
                    print(f"Pesan '{deleted_mail['subject']}' telah dihapus.")
                else:
                    print("Nomor pesan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        # --- [7] EXPORT MAILBOX ---
        elif choice == '7':
            # tulis isi my_inbox dan my_outbox ke file teks
            print(f"\n--- Mengekspor Mailbox {username} ---")
            if not my_inbox and not my_outbox:
                print("Inbox dan Outbox kosong."); continue
            
            filename = f"{username}_mailbox_export.txt"
            try:
                # buka file untuk ditulis ('w')
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"=== Arsip Mailbox untuk {username} ===\n")
                    f.write(f"Diekspor pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    # tulis bagian Inbox
                    f.write("========== INBOX ==========\n")
                    if not my_inbox: f.write("(Inbox Kosong)\n\n")
                    else:
                        for i, mail in enumerate(my_inbox):
                            # format penulisan pesan inbox
                            f.write(f"--- Pesan #{i+1} ---\n")
                            f.write(f"Status: {'UNREAD' if not mail['read'] else 'READ'}\n")
                            f.write(f"Dari: {mail.get('from', 'Unknown')}\n")
                            f.write(f"Subject: {mail.get('subject', 'N/A')}\n")
                            f.write(f"Pesan: {mail.get('msg', '(Kosong)')}\n")
                            f.write("---------------------\n\n")

                    # tulis bagian Outbox
                    f.write("========= OUTBOX ==========\n")
                    if not my_outbox: f.write("(Outbox Kosong)\n\n")
                    else:
                        for i, m in enumerate(my_outbox):
                            # format penulisan pesan outbox
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
            print("Keluar dari UR-Mail...")
            break

async def main(host, port):
    """Coroutine utama untuk inisialisasi client"""
    print(f"Menghubungkan ke Server {host}:{port} ...")
    reader, writer = None, None
    try:
        # connect ke server
        reader, writer = await asyncio.open_connection(host, port)
        print("[OK] Connected!")
        
        # buat task untuk receiver dan UI agar berjalan paralel
        receiver_task = asyncio.create_task(receive_messages(reader))
        ui_task = asyncio.create_task(user_interface(writer))

        # menunggu sampai salah satu task selesai (UI saat user pilih Exit)
        done, pending = await asyncio.wait(
            [receiver_task, ui_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # membatalkan task yang masih berjalan (cthnya receiver_task)
        for task in pending:
            task.cancel()

    except Exception as e:
        print(f"[ERR] Gagal Connect: {e}")
    finally:
        if writer:
            print("Menutup koneksi...")
            writer.close()
            await writer.wait_closed()
            print("Koneksi ditutup.")

if __name__ == '__main__':
    # Setup argumen command line
    parser = argparse.ArgumentParser(description="UR-Mail Client")
    parser.add_argument('--host', type=str, default='127.0.0.1', help='IP Server Tujuan')
    parser.add_argument('--port', type=int, default=8888, help='Port Server Tujuan')
    args = parser.parse_args()

    try:
        # config untuk Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # jalanin coroutine utama 'main'
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        # jika di close dengan Ctrl+C
        print("\nProgram dihentikan oleh user (Ctrl+C).")