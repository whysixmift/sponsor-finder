import os
import json
import asyncio
from functools import wraps
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from app.config.settings import settings
from app.database.db import async_session_maker
from app.database.models import Sponsor, ProposalProfile, EmailQueue, AISponsorMatch
from app.agents.access_control_agent import access_control_agent
from app.agents.proposal_agent import proposal_agent
from app.agents.matching_agent import matching_agent
from app.agents.sponsor_discovery_agent import sponsor_discovery_agent
from app.agents.email_drafting_agent import email_drafting_agent
from app.agents.email_dispatch_agent import email_dispatch_agent
from app.services.sponsor_service import sponsor_service
from app.services.google_auth_service import google_auth_service
from app.services.email_service import email_service
from app.utils.logger import logger

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
        if update.effective_user.id != settings.TELEGRAM_ADMIN_ID:
            if update.effective_message:
                await update.effective_message.reply_text("⛔ <b>Akses Ditolak:</b> Khusus Administrator.", parse_mode="HTML")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def whitelist_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
        user_id = update.effective_user.id
        username = update.effective_user.username
        allowed = await access_control_agent.is_allowed(user_id, username)
        if not allowed:
            user_display = f"@{username}" if username else f"ID {user_id}"
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"🔒 <b>Akses Terbatas (Private Beta)</b>\n\n"
                    f"Akun Anda ({user_display}) belum terdaftar di whitelist Sponsor Finder.\n"
                    f"Silakan hubungi Administrator untuk mendapatkan akses.",
                    parse_mode="HTML"
                )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "Partner"

    keyboard = [
        [
            InlineKeyboardButton("📄 Unggah Proposal", callback_data="btn_upload_info"),
            InlineKeyboardButton("🎯 Cari Sponsor Cocok", callback_data="btn_run_match")
        ],
        [
            InlineKeyboardButton("🏢 Direktori Sponsor", callback_data="btn_catalog_tech"),
            InlineKeyboardButton("✉️ Antrean Outreach", callback_data="btn_outreach_list")
        ],
        [
            InlineKeyboardButton("🔍 Live Web Discovery", callback_data="btn_run_discovery"),
            InlineKeyboardButton("🔗 Connect Gmail", callback_data="btn_connect_google")
        ],
        [
            InlineKeyboardButton("⭐ Sponsor Favorit", callback_data="btn_favorites"),
            InlineKeyboardButton("⚙️ Status Proposal", callback_data="btn_proposal_status")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 <b>Halo {name}! Selamat datang di Sponsor Finder</b>\n\n"
        f"Sponsor Finder adalah AI Multi-Agent otonom untuk mencari dan menghubungkan event Anda "
        f"dengan perusahaan sponsor yang tepat (Indonesia & Global).\n\n"
        f"<b>Cara Kerja Cepat:</b>\n"
        f"1️⃣ <b>Kirimkan Dokumen Proposal</b> (.pdf / .docx) langsung ke chat ini.\n"
        f"2️⃣ Bot mengekstrak demografi peserta, target dana, dan tema acara secara otomatis.\n"
        f"3️⃣ AI mengevaluasi kesesuaian brand & menghitung skor keselarasan sponsorship.\n"
        f"4️⃣ Dapatkan draft surat/email penawaran sponsorship yang dipersonalisasi dengan proposal terlampir!\n\n"
        f"Pilih menu di bawah atau kirim file proposal Anda sekarang 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 <b>Panduan Perintah Sponsor Finder:</b>\n\n"
        "• <b>Kirim File (.pdf / .docx):</b> Langsung upload proposal event Anda ke chat.\n"
        "• <code>/proposal</code> : Lihat detail & ringkasan proposal yang aktif.\n"
        "• <code>/match</code> : Jalankan AI matching untuk mencari sponsor paling relevan.\n"
        "• <code>/catalog</code> : Jelajahi katalog sponsor berdasarkan industri & kategori.\n"
        "• <code>/discover</code> : Crawl web untuk menemukan program CSR & kemitraan baru.\n"
        "• <code>/outreach</code> : Cek draft email penawaran dan kirim ke pihak sponsor.\n"
        "• <code>/connect_google</code> : Hubungkan akun Gmail untuk 1-click email dispatch.\n"
        "• <code>/smtp</code> : Pengaturan akun email kustom (SMTP).\n"
        "• <code>/favorites</code> : Daftar sponsor yang Anda simpan/tandai.\n"
        "• <code>/status</code> : Status sistem dan status agen AI."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

@whitelist_required
async def proposal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with async_session_maker() as session:
        proposal = await proposal_agent.get_user_proposal(session, user_id)

    if not proposal:
        await update.message.reply_text(
            "📂 <b>Belum Ada Proposal yang Diunggah</b>\n\n"
            "Silakan kirimkan dokumen proposal kegiatan Anda dalam format <b>PDF (.pdf)</b> "
            "atau <b>Word (.docx)</b> langsung ke chat ini.",
            parse_mode="HTML"
        )
        return

    tiers_formatted = ""
    if proposal.sponsorship_tiers:
        try:
            tiers = json.loads(proposal.sponsorship_tiers)
            if isinstance(tiers, dict):
                tiers_formatted = "\n".join([f"  • <b>{k}:</b> {v}" for k, v in tiers.items()])
        except Exception:
            tiers_formatted = proposal.sponsorship_tiers

    resp = (
        f"📋 <b>Detail Proposal Aktif Anda:</b>\n\n"
        f"<b>Judul Event:</b> {proposal.title}\n"
        f"<b>Tipe Kegiatan:</b> {proposal.event_type}\n"
        f"<b>Target Audiens:</b> {proposal.target_audience or '-'}\n"
        f"<b>Estimasi Peserta:</b> {proposal.expected_attendees or '-'}\n"
        f"<b>Lokasi & Tanggal:</b> {proposal.location or '-'} | {proposal.event_date or '-'}\n"
        f"<b>Target Anggaran:</b> {proposal.requested_budget or '-'}\n\n"
        f"<b>Paket Sponsorship:</b>\n{tiers_formatted or '  • Belum dispesifikasi'}\n\n"
        f"<b>Ringkasan AI:</b>\n<i>{proposal.summary or '-'}</i>"
    )
    keyboard = [[InlineKeyboardButton("🎯 Cari Sponsor Sekarang", callback_data="btn_run_match")]]
    await update.message.reply_text(resp, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

@whitelist_required
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    doc = message.document
    if not doc:
        return

    filename = doc.file_name or "proposal.pdf"
    ext = filename.lower().split(".")[-1]
    if ext not in ["pdf", "docx", "doc", "txt"]:
        await message.reply_text(
            "⚠️ Format file tidak didukung. Harap unggah proposal dalam format <b>PDF (.pdf)</b> atau <b>DOCX (.docx)</b>.",
            parse_mode="HTML"
        )
        return

    status_msg = await message.reply_text("⏳ <i>Mengunduh dan mengekstrak dokumen proposal Anda...</i>", parse_mode="HTML")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        await status_msg.edit_text("🧠 <i>Menganalisis profil audiens, tema, dan paket tier sponsor dengan AI...</i>", parse_mode="HTML")

        user_id = update.effective_user.id
        async with async_session_maker() as session:
            proposal = await proposal_agent.ingest_proposal(session, user_id, filename, bytes(file_bytes))

        keyboard = [
            [InlineKeyboardButton("🎯 Jalankan AI Match Sponsor", callback_data="btn_run_match")],
            [InlineKeyboardButton("📋 Lihat Rincian Ekstraksi", callback_data="btn_proposal_status")]
        ]
        await status_msg.edit_text(
            f"✅ <b>Proposal Berhasil Disimpan & Dianalisis!</b>\n\n"
            f"<b>Event:</b> {proposal.title}\n"
            f"<b>Kategori:</b> {proposal.event_type}\n"
            f"<b>Audiens:</b> {proposal.target_audience or 'Umum / Komunitas'}\n"
            f"<b>Ringkasan:</b> {proposal.summary or '-'}\n\n"
            f"Siap mencocokkan dengan sponsor yang relevan?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error handling proposal upload: {e}")
        await status_msg.edit_text(f"❌ Gagal memproses proposal: {str(e)}")

@whitelist_required
async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id

    status_msg = await message.reply_text("🔍 <i>Mengevaluasi kecocokan brand dan nilai ROI sponsorship...</i>", parse_mode="HTML")

    matches = await matching_agent.match_sponsors_for_user(user_id=user_id)

    if not matches:
        await status_msg.edit_text(
            "⚠️ Belum ada sponsor dengan skor di atas ambang batas (70%).\n"
            "Coba jalankan <code>/discover</code> untuk menemukan lebih banyak brand atau perbarui proposal Anda.",
            parse_mode="HTML"
        )
        return

    await status_msg.edit_text(f"🎉 <b>Ditemukan {len(matches)} Sponsor Potensial Paling Cocok:</b>", parse_mode="HTML")

    for match, sponsor in matches[:5]:
        reg_flag = "🇮🇩" if sponsor.region == "Indonesia" else "🌐"
        text = (
            f"🏢 <b>{sponsor.name}</b> {reg_flag}\n"
            f"<b>Industri:</b> {sponsor.category} | <b>Wilayah:</b> {sponsor.region}\n"
            f"<b>Skor Kecocokan AI:</b> ⭐️ <b>{match.score}%</b> ({match.priority.upper()})\n"
            f"<b>Rekomendasi Tier:</b> {match.suggested_tier}\n"
            f"<b>Sudut Penawaran (Value Angle):</b>\n<i>{match.value_proposition_angle}</i>\n\n"
            f"<b>Alasan Relevansi:</b>\n{match.reason}\n"
            f"<b>Email:</b> <code>{sponsor.contact_email or 'Belum ada'}</code>"
        )

        buttons = []
        row1 = []
        if sponsor.contact_email:
            row1.append(InlineKeyboardButton("✉️ Buat Pitch Email", callback_data=f"draft_{sponsor.id}"))
        if sponsor.website:
            row1.append(InlineKeyboardButton("🌐 Web", url=sponsor.website))
        buttons.append(row1)

        buttons.append([
            InlineKeyboardButton("⭐ Simpan Favorit", callback_data=f"fav_{sponsor.id}")
        ])

        await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

@whitelist_required
async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("💻 Tech & Cloud", callback_data="cat_Tech"),
            InlineKeyboardButton("🥤 FMCG & Beverage", callback_data="cat_FMCG")
        ],
        [
            InlineKeyboardButton("🏦 Banking & Fintech", callback_data="cat_Banking"),
            InlineKeyboardButton("🎮 Gaming & Hardware", callback_data="cat_Gaming")
        ],
        [
            InlineKeyboardButton("📱 Telco & Digital", callback_data="cat_Telecommunication"),
            InlineKeyboardButton("🌿 CSR & Foundation", callback_data="cat_CSR")
        ],
        [
            InlineKeyboardButton("🌐 Semua Sponsor Global", callback_data="cat_Global"),
            InlineKeyboardButton("🇮🇩 Semua Sponsor Indonesia", callback_data="cat_Indonesia")
        ]
    ]
    await update.effective_message.reply_text(
        "📚 <b>Direktori Perusahaan Sponsor:</b>\n\nPilih kategori industri sponsor yang ingin Anda jelajahi:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@whitelist_required
async def outreach_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with async_session_maker() as session:
        from sqlalchemy import select
        stmt = select(EmailQueue, Sponsor).join(Sponsor, EmailQueue.sponsor_id == Sponsor.id).where(EmailQueue.user_id == user_id).order_by(EmailQueue.id.desc()).limit(10)
        res = await session.execute(stmt)
        queue_items = list(res.all())

    if not queue_items:
        await update.effective_message.reply_text(
            "📭 <b>Antrean Outreach Kosong</b>\n\n"
            "Anda belum memiliki draft penawaran sponsorship. "
            "Gunakan perintah <code>/match</code> lalu klik <b>'✉️ Buat Pitch Email'</b> untuk menghasilkan draft.",
            parse_mode="HTML"
        )
        return

    await update.effective_message.reply_text(f"📨 <b>Daftar Draft & Riwayat Pengiriman Email ({len(queue_items)}):</b>", parse_mode="HTML")

    for email_rec, sponsor in queue_items:
        status_icon = "📝 Draft" if email_rec.status == "draft" else ("✅ Terkirim" if email_rec.status == "sent" else f"⚠️ {email_rec.status}")
        text = (
            f"<b>Tujuan:</b> {sponsor.name} ({email_rec.recipient_email})\n"
            f"<b>Subjek:</b> {email_rec.subject}\n"
            f"<b>Status:</b> {status_icon}\n"
            f"<b>Lampiran:</b> {os.path.basename(email_rec.attachment_path) if email_rec.attachment_path else 'Tidak ada'}"
        )
        buttons = []
        if email_rec.status == "draft":
            buttons.append([
                InlineKeyboardButton("👀 Lihat Isi Draft", callback_data=f"view_draft_{email_rec.id}"),
                InlineKeyboardButton("🚀 Kirim Sekarang", callback_data=f"send_email_{email_rec.id}")
            ])
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@whitelist_required
async def discover_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.effective_message.reply_text("🌐 <i>Melakukan web crawling untuk mencari program sponsorship & CSR baru...</i>", parse_mode="HTML")
    count = await sponsor_discovery_agent.run_discovery(limit=4)
    if count > 0:
        await status_msg.edit_text(f"✅ <b>Berhasil menemukan {count} perusahaan sponsor baru!</b>\nPeriksa katalog di <code>/catalog</code> atau jalankan <code>/match</code>.", parse_mode="HTML")
    else:
        await status_msg.edit_text("ℹ️ Tidak ditemukan entri baru pada sesi crawling ini. Database katalog sudah termutakhirkan.", parse_mode="HTML")

@whitelist_required
async def connect_google_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    auth_url = google_auth_service.get_authorization_url(user_id)
    if not auth_url:
        await update.effective_message.reply_text(
            "⚠️ Google OAuth belum dikonfigurasi di file <code>.env</code>.\n"
            "Silakan gunakan pengaturan SMTP manual melalui <code>/smtp</code> atau minta Admin memasukkan GOOGLE_CLIENT_ID.",
            parse_mode="HTML"
        )
        return

    keyboard = [[InlineKeyboardButton("🔗 Otorisasi Akun Google", url=auth_url)]]
    await update.effective_message.reply_text(
        "📬 <b>Integrasi Google SSO (Gmail API)</b>\n\n"
        "Hubungkan akun Gmail Anda agar bot dapat mengirimkan surat penawaran sponsorship "
        "langsung dari kotak masuk Anda dengan proposal PDF terlampir secara otomatis.\n\n"
        "Klik tombol di bawah untuk memberikan otorisasi:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "btn_upload_info":
        await query.message.reply_text("Silakan kirimkan dokumen proposal (.pdf/.docx) Anda langsung ke chat ini.")

    elif data == "btn_run_match":
        await match_command(update, context)

    elif data == "btn_proposal_status":
        await proposal_command(update, context)

    elif data == "btn_outreach_list":
        await outreach_command(update, context)

    elif data == "btn_run_discovery":
        await discover_command(update, context)

    elif data == "btn_connect_google":
        await connect_google_command(update, context)

    elif data == "btn_favorites":
        async with async_session_maker() as session:
            favs = await sponsor_service.get_user_favorites(session, user_id)
        if not favs:
            await query.message.reply_text("⭐ Anda belum menyimpan sponsor favorit. Klik tombol '⭐ Simpan Favorit' pada hasil pencarian.")
        else:
            txt = "⭐ <b>Sponsor Favorit Anda:</b>\n\n"
            for s in favs:
                txt += f"• <b>{s.name}</b> ({s.category}) - {s.contact_email or 'No email'}\n"
            await query.message.reply_text(txt, parse_mode="HTML")

    elif data.startswith("draft_"):
        sponsor_id = int(data.split("_")[1])
        status_msg = await query.message.reply_text("✍️ <i>Menyusun draft cold email sponsorship yang dipersonalisasi...</i>", parse_mode="HTML")
        try:
            async with async_session_maker() as session:
                draft = await email_drafting_agent.create_draft(session, user_id, sponsor_id)

            buttons = [
                [
                    InlineKeyboardButton("👀 Tinjau Email", callback_data=f"view_draft_{draft.id}"),
                    InlineKeyboardButton("🚀 Kirim Sekarang", callback_data=f"send_email_{draft.id}")
                ]
            ]
            await status_msg.edit_text(
                f"✅ <b>Draft Email Penawaran Berhasil Dibuat!</b>\n\n"
                f"<b>Subjek:</b> {draft.subject}\n"
                f"<b>Penerima:</b> {draft.recipient_email}\n"
                f"<b>Lampiran:</b> {os.path.basename(draft.attachment_path) if draft.attachment_path else 'Tidak ada'}\n\n"
                f"Klik 'Tinjau Email' untuk membaca isi surat atau 'Kirim Sekarang' untuk mengirim.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ Gagal membuat draft: {e}")

    elif data.startswith("view_draft_"):
        draft_id = int(data.split("_")[2])
        async with async_session_maker() as session:
            from sqlalchemy import select
            stmt = select(EmailQueue).where(EmailQueue.id == draft_id)
            res = await session.execute(stmt)
            draft = res.scalar_one_or_none()

        if draft:
            text = (
                f"📄 <b>Isi Draft Email #{draft.id}:</b>\n\n"
                f"<b>Kepada:</b> {draft.recipient_email}\n"
                f"<b>Subjek:</b> {draft.subject}\n\n"
                f"{draft.body}\n\n"
                f"📎 <b>Lampiran:</b> {os.path.basename(draft.attachment_path) if draft.attachment_path else '-'}"
            )
            buttons = [[InlineKeyboardButton("🚀 Kirim Email Ini", callback_data=f"send_email_{draft.id}")]]
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("send_email_"):
        draft_id = int(data.split("_")[2])
        status_msg = await query.message.reply_text("📤 <i>Mengirim email sponsorship via Gmail / SMTP...</i>", parse_mode="HTML")
        try:
            async with async_session_maker() as session:
                success = await email_dispatch_agent.send_email(session, draft_id)
            if success:
                await status_msg.edit_text("🎉 <b>Email sponsorship berhasil dikirimkan bersama lampiran proposal!</b>", parse_mode="HTML")
        except Exception as e:
            await status_msg.edit_text(f"❌ Pengiriman email gagal: {e}")

    elif data.startswith("fav_"):
        sponsor_id = int(data.split("_")[1])
        async with async_session_maker() as session:
            now_fav = await sponsor_service.toggle_favorite(session, user_id, sponsor_id)
        state_str = "ditambahkan ke" if now_fav else "dihapus dari"
        await query.message.reply_text(f"⭐ Sponsor berhasil {state_str} daftar favorit Anda.")

    elif data.startswith("cat_"):
        cat_key = data.split("_")[1]
        async with async_session_maker() as session:
            if cat_key in ["Indonesia", "Global"]:
                sponsors = await sponsor_service.get_all_sponsors(session, region=cat_key, limit=8)
            else:
                sponsors = await sponsor_service.get_all_sponsors(session, category=cat_key, limit=8)

        if not sponsors:
            await query.message.reply_text(f"Belum ada sponsor di kategori '{cat_key}'.")
            return

        txt = f"🏢 <b>Daftar Sponsor ({cat_key}):</b>\n\n"
        for s in sponsors:
            txt += f"• <b>{s.name}</b> ({s.region})\n  Email: <code>{s.contact_email or '-'}</code>\n  Tipe: {s.typical_sponsorship or '-'}\n\n"
        await query.message.reply_text(txt, parse_mode="HTML")

def setup_bot(application: Application):
    """Register all command and message handlers on the telegram bot application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("proposal", proposal_command))
    application.add_handler(CommandHandler("match", match_command))
    application.add_handler(CommandHandler("catalog", catalog_command))
    application.add_handler(CommandHandler("outreach", outreach_command))
    application.add_handler(CommandHandler("discover", discover_command))
    application.add_handler(CommandHandler("connect_google", connect_google_command))

    # File uploads
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))

    # Inline button callbacks
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    logger.info("Telegram Bot handlers registered successfully.")
