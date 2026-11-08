# Sponsor Finder - Multi-Tenant AI Event Sponsorship Hunter SaaS

**Sponsor Finder** adalah platform SaaS otomatisasi pencarian sponsor korporat/brand (Indonesia & Global) dan pengiriman cold email penawaran kemitraan berbasis Multi-Agent System (`1 Feature = 1 Agent`). Sistem ini bekerja dengan menerima dokumen proposal kegiatan (`.pdf`, `.docx`, atau teks), mengekstrak demografi audiens serta kebutuhan anggaran/tier secara otomatis, melakukan pencocokan semantik AI menggunakan LLM (OpenRouter / Gemini / Heuristic Engine), menyusun draf email penawaran personal berlampiran proposal fisik, serta menyediakan antarmuka Telegram Bot (Port 20138) dan Web SaaS Admin Dashboard (Port 20139).

---

## Arsitektur Dual-Port VPS

Aplikasi dirancang dengan arsitektur dual-service independen yang dapat dideploy di VPS:

```
                              +-------------------------------------------+
                              |              VPS HOST SERVER              |
                              +-------------------------------------------+
                                            /               \
                                           /                 \
                                  PORT 20138                 PORT 20139
                                       |                          |
                                       v                          v
                        +----------------------------+  +----------------------------+
                        |    TELEGRAM BOT BRANCH     |  |       WEB SAAS BRANCH      |
                        | - Bot Polling / Webhook    |  | - FastAPI Web Server       |
                        | - Health Service           |  | - Admin Dashboard          |
                        | - Telemetri Status         |  | - Google OAuth2 Callbacks  |
                        +----------------------------+  +----------------------------+
                                       \                          /
                                        \                        /
                                         v                      v
                                +-----------------------------------+
                                |     SHARED MULTI-AGENT ENGINE     |
                                |       (1 Feature = 1 Agent)       |
                                +-----------------------------------+
                                                  |
                                                  v
                                +-----------------------------------+
                                |    SQLAlchemy 2.0 (SQLite / DB)   |
                                +-----------------------------------+
```

- **Port `20138` (Bot Branch)**: Menjalankan listener Telegram Bot dan endpoint HTTP `/health` serta `/metrics`.
- **Port `20139` (Web SaaS Branch)**: Menjalankan antarmuka SaaS Web, Google OAuth2 callback, dan Admin Dashboard interaktif.

---

## Multi-Agent Architecture ("1 Feature = 1 Agent")

Seluruh fungsionalitas modular diisolasi ke dalam agen-agen otonom di `app/agents/`, mewarisi `BaseAgent` dengan pelacakan telemetri real-time:

| Agen | File | Deskripsi Fitur |
| :--- | :--- | :--- |
| **ProposalAgent** | [`app/agents/proposal_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/proposal_agent.py) | Ingesti dokumen proposal event (`.pdf`, `.docx`), penyimpanan file fisik di `data/proposals/`, ekstraksi demografi peserta, tanggal, lokasi, dan paket tier sponsor. |
| **MatchingAgent** | [`app/agents/matching_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/matching_agent.py) | Evaluasi kesesuaian semantik antara proposal dan calon sponsor (irisan target pasar, brand alignment, ROI, dan penentuan paket sponsorship terbaik). |
| **SponsorDiscoveryAgent** | [`app/agents/sponsor_discovery_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/sponsor_discovery_agent.py) | Web discovery otonom untuk mencari halaman kemitraan korporat, kontak email CSR, dan program sponsor baru. |
| **SponsorScraperAgent** | [`app/agents/sponsor_scraper_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/sponsor_scraper_agent.py) | Agregator peluang sponsorship terbuka, developer grants, dan kompetisi. |
| **EmailDraftingAgent** | [`app/agents/email_drafting_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/email_drafting_agent.py) | Pembuatan draf surat/cold email penawaran kemitraan yang dipersonalisasi sesuai profil brand dan otomatis melampirkan file PDF proposal asli. |
| **EmailDispatchAgent** | [`app/agents/email_dispatch_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/email_dispatch_agent.py) | Pengiriman email otomatis multi-protokol: prioritas via Google SSO (Gmail API `gmail.send`), fallback ke SMTP terenkripsi. |
| **AccessControlAgent** | [`app/agents/access_control_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/access_control_agent.py) | Whitelist akses bot berbasis SaaS, mendukung otentikasi via Telegram Username (`@user`) maupun User ID (numerik). |
| **SchedulerAgent** | [`app/agents/scheduler_agent.py`](file:///home/avrjulian/sponsor-finder/app/agents/scheduler_agent.py) | Penjadwalan berkala di latar belakang untuk web crawling dan pemeliharaan antrean email. |

---

## Alur Kerja Utama Pengguna (User Flow)

1. **Upload Dokumen Proposal**:
   - Pengguna mengirim file proposal kegiatan (`.pdf` atau `.docx`) langsung ke Telegram Bot.
   - `ProposalAgent` mengekstrak teks, mengidentifikasi tema (misal: Hackathon, Seminar, Konser, Turnamen Esports), demografi audiens (misal: Mahasiswa IT, Gen-Z), serta estimasi biaya/tier sponsor.
2. **AI Semantic Matching**:
   - Menjalankan perintah `/match`.
   - `MatchingAgent` mencocokkan profil proposal dengan katalog brand (Indonesia & Global) seperti FMCG (Paragon, Nutrifood, Indofood), Telco (Telkomsel), Bank/Fintech (BCA, Mandiri, DANA), Tech (GitHub, Microsoft, Cloudflare, ASUS ROG), dsb.
   - Menampilkan skor kecocokan (0-100%), rekomendasi tier, serta sudut penawaran (value angle).
3. **Penyusunan Cold Pitch & Auto-Attach**:
   - Pengguna mengklik tombol **"✉️ Buat Pitch Email"**.
   - `EmailDraftingAgent` menyusun surat penawaran resmi dan menautkan file proposal fisik sebagai lampiran MIME.
4. **Pengiriman Email (Outreach)**:
   - Pengguna dapat menghubungkan akun Google mereka via `/connect_google` (Gmail API) atau mengatur SMTP kustom (`/smtp`).
   - Email dikirim langsung dari inbox pengguna ke email PIC brand/CSR tujuan.

---

## Web SaaS & Admin Dashboard (Port 20139)

Akses Admin Dashboard tersedia melalui browser di:
```
http://<IP_VPS_ATAU_DOMAIN>:20139/admin
```

- **Password Admin Default**: `uranium235aregoated`
- **Fitur Dashboard**:
  - **Overview Metrics**: Total sponsor di katalog, proposal masuk, antrean email, dan pengguna terdaftar.
  - **Sponsor Catalog**: Daftar lengkap perusahaan mitra, filter wilayah (Indonesia/Global), industri, dan form penambahan sponsor baru.
  - **Email Queue Management**: Pemantauan status draf, pengiriman email, dan file lampiran proposal.
  - **User Whitelist Management**: Tambah/nonaktifkan akses anggota tim menggunakan Telegram Username atau User ID.
  - **Environment (.env) Editor**: Edit token bot, API key LLM, kredensial Google, dan port langsung dari browser.
  - **Agent Telemetry**: Monitoring status hidup dan histori eksekusi dari ke-8 agen otonom.

---

## Cara Menjalankan Aplikasi

### 1. Masuk ke Direktori Proyek
```bash
cd /home/avrjulian/sponsor-finder
```

### 2. Jalankan Mode Lengkap (Dual-Port Concurrent)
```bash
.venv/bin/python main.py all
```
*Atau jalankan branch tertentu secara spesifik:*
- **Web SaaS Saja**: `.venv/bin/python main.py web`
- **Bot Telegram Saja**: `.venv/bin/python main.py bot`

### 3. Menjalankan Automated Test Suite
```bash
.venv/bin/pytest -v
```
