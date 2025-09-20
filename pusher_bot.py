import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
from datetime import datetime
import json
import asyncio
import sqlite3
from pathlib import Path

# Miljøvariabler og token
load_dotenv()  # Load from .env file if exists
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("⚠️ DISCORD_TOKEN ikke fundet i miljøvariabler!")
    print("Sørg for at sætte DISCORD_TOKEN som miljøvariabel eller i .env fil")
    exit(1)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Kanal og rolle IDs
MEDLEM_ROLLE_ID = 1419002926675791993
PUSHER_KANAL_ID = 1419000630927691787
MEDLEM_KANAL_ID = 1419003264690556999
PRIVAT_KATEGORI_ID = 1419003473386799267
ADMIN_ROLLE_ID = 1418989096306741299
PUSHER_STATS_KANAL_ID = 1419012741007409314

# Database setup
DATA_DIR = Path("/data") if Path("/data").exists() else Path(".")
DB_PATH = DATA_DIR / "pusher_bot.db"

# Default permanent jobs
DEFAULT_PERMANENT_JOBS = [
    "🚗 Køre rundt og sælge stoffer",
    "💰 Hjælpe med money wash",
    "🏠 Hjælpe med hus raids",
    "⚔️ Hjælpe med gang wars",
    "📦 Hjælpe med leveringer",
    "🔫 Hjælpe med våben handel",
    "🎯 Hjælpe med contracts"
]

def init_database():
    """Initialize SQLite database"""
    try:
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permanent_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_text TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS member_jobs (
                id TEXT PRIMARY KEY,
                titel TEXT NOT NULL,
                beskrivelse TEXT NOT NULL,
                belonning TEXT,
                oprettet_af INTEGER NOT NULL,
                oprettet_navn TEXT NOT NULL,
                status TEXT DEFAULT 'ledig',
                pusher_id INTEGER,
                pusher_navn TEXT,
                privat_kanal_id INTEGER,
                oprettet_tid TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                taget_tid TIMESTAMP,
                job_number INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS completed_jobs (
                id TEXT PRIMARY KEY,
                titel TEXT NOT NULL,
                beskrivelse TEXT NOT NULL,
                belonning TEXT,
                oprettet_af INTEGER NOT NULL,
                oprettet_navn TEXT NOT NULL,
                pusher_id INTEGER NOT NULL,
                pusher_navn TEXT NOT NULL,
                completed_tid TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                job_number INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pusher_stats (
                pusher_id INTEGER PRIMARY KEY,
                pusher_navn TEXT NOT NULL,
                total_jobs INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # Insert default permanent jobs if none exist
        cursor.execute("SELECT COUNT(*) FROM permanent_jobs")
        if cursor.fetchone()[0] == 0:
            for job in DEFAULT_PERMANENT_JOBS:
                cursor.execute("INSERT OR IGNORE INTO permanent_jobs (job_text) VALUES (?)", (job,))
        
        # Initialize job counter if not exists
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('job_counter', '1')")
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
        
    except Exception as e:
        print(f"❌ Fejl ved database initialisering: {e}")

def get_permanent_jobs():
    """Get all permanent jobs from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT job_text FROM permanent_jobs ORDER BY id")
        jobs = [row[0] for row in cursor.fetchall()]
        conn.close()
        return jobs
    except Exception as e:
        print(f"Fejl ved hentning af permanente jobs: {e}")
        return DEFAULT_PERMANENT_JOBS

def add_permanent_job(job_text):
    """Add permanent job to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO permanent_jobs (job_text) VALUES (?)", (job_text,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False  # Job already exists
    except Exception as e:
        print(f"Fejl ved tilføjelse af permanent job: {e}")
        return False

def update_permanent_job(old_text, new_text):
    """Update permanent job in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE permanent_jobs SET job_text = ? WHERE job_text = ?", (new_text, old_text))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"Fejl ved opdatering af permanent job: {e}")
        return False

def remove_permanent_job(job_text):
    """Remove permanent job from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM permanent_jobs WHERE job_text = ?", (job_text,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"Fejl ved fjernelse af permanent job: {e}")
        return False

def get_member_jobs():
    """Get all member jobs from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titel, beskrivelse, belonning, oprettet_af, oprettet_navn, 
                   status, pusher_id, pusher_navn, privat_kanal_id, oprettet_tid, 
                   taget_tid, job_number
            FROM member_jobs 
            ORDER BY job_number
        """)
        jobs = []
        for row in cursor.fetchall():
            job = {
                "id": row[0], "titel": row[1], "beskrivelse": row[2], "belonning": row[3],
                "oprettet_af": row[4], "oprettet_navn": row[5], "status": row[6],
                "pusher_id": row[7], "pusher_navn": row[8], "privat_kanal_id": row[9],
                "oprettet_tid": row[10], "taget_tid": row[11], "job_number": row[12]
            }
            jobs.append(job)
        conn.close()
        return jobs
    except Exception as e:
        print(f"Fejl ved hentning af medlem jobs: {e}")
        return []

def add_member_job(job_data):
    """Add member job to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get next job number
        cursor.execute("SELECT value FROM settings WHERE key = 'job_counter'")
        job_counter = int(cursor.fetchone()[0])
        
        cursor.execute("""
            INSERT INTO member_jobs 
            (id, titel, beskrivelse, belonning, oprettet_af, oprettet_navn, job_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_data["id"], job_data["titel"], job_data["beskrivelse"],
            job_data["belonning"], job_data["oprettet_af"], job_data["oprettet_navn"],
            job_counter
        ))
        
        # Update job counter
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'job_counter'", (str(job_counter + 1),))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Fejl ved tilføjelse af medlem job: {e}")
        return False

def update_member_job_status(job_id, status, pusher_id=None, pusher_navn=None):
    """Update member job status in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if pusher_id and pusher_navn:
            cursor.execute("""
                UPDATE member_jobs 
                SET status = ?, pusher_id = ?, pusher_navn = ?, taget_tid = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, pusher_id, pusher_navn, job_id))
        else:
            cursor.execute("UPDATE member_jobs SET status = ? WHERE id = ?", (status, job_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"Fejl ved opdatering af job status: {e}")
        return False

def complete_member_job(job_id):
    """Complete a member job and update stats"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get job data
        cursor.execute("SELECT * FROM member_jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        if not job_row:
            conn.close()
            return False
        
        # Move to completed_jobs
        cursor.execute("""
            INSERT INTO completed_jobs 
            (id, titel, beskrivelse, belonning, oprettet_af, oprettet_navn, 
             pusher_id, pusher_navn, job_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_row[0], job_row[1], job_row[2], job_row[3], job_row[4], 
              job_row[5], job_row[7], job_row[8], job_row[12]))
        
        # Update pusher stats
        cursor.execute("""
            INSERT OR REPLACE INTO pusher_stats (pusher_id, pusher_navn, total_jobs)
            VALUES (?, ?, COALESCE((SELECT total_jobs FROM pusher_stats WHERE pusher_id = ?), 0) + 1)
        """, (job_row[7], job_row[8], job_row[7]))
        
        # Remove from member_jobs
        cursor.execute("DELETE FROM member_jobs WHERE id = ?", (job_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Fejl ved færdiggørelse af job: {e}")
        return False

def get_member_job_by_id(job_id):
    """Get specific member job by ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titel, beskrivelse, belonning, oprettet_af, oprettet_navn, 
                   status, pusher_id, pusher_navn, privat_kanal_id, oprettet_tid, 
                   taget_tid, job_number
            FROM member_jobs WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0], "titel": row[1], "beskrivelse": row[2], "belonning": row[3],
                "oprettet_af": row[4], "oprettet_navn": row[5], "status": row[6],
                "pusher_id": row[7], "pusher_navn": row[8], "privat_kanal_id": row[9],
                "oprettet_tid": row[10], "taget_tid": row[11], "job_number": row[12]
            }
        return None
    except Exception as e:
        print(f"Fejl ved hentning af job: {e}")
        return None

@bot.event
async def on_ready():
    print(f"Pusher Bot er online som {bot.user}")
    
    # Initialize database
    init_database()
    
    # Setup kanaler
    await setup_pusher_kanal()
    await setup_medlem_kanal()
    await setup_pusher_stats_kanal()

async def setup_pusher_kanal():
    """Setup pusher kanal med job oversigt"""
    kanal = bot.get_channel(PUSHER_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Pusher kanal med ID {PUSHER_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Clear channel
        await kanal.purge()
        print(f"🧹 Pusher kanal {kanal.name} er ryddet.")
    except Exception as e:
        print(f"❌ Fejl under rydning af pusher kanal: {e}")
    
    # Send pusher embed
    await send_pusher_embed(kanal)

async def setup_medlem_kanal():
    """Setup medlem kanal med knap til at oprette jobs"""
    kanal = bot.get_channel(MEDLEM_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Medlem kanal med ID {MEDLEM_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Clear channel
        await kanal.purge()
        print(f"🧹 Medlem kanal {kanal.name} er ryddet.")
    except Exception as e:
        print(f"❌ Fejl under rydning af medlem kanal: {e}")
    
    # Send medlem embed
    await send_medlem_embed(kanal)

class PusherJobView(View):
    def __init__(self):
        super().__init__(timeout=None)

class MedlemView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ Opret Opgave", style=discord.ButtonStyle.primary, emoji="📝")
    async def opret_opgave(self, interaction: discord.Interaction, button: Button):
        # Tjek om brugeren har medlem rollen
        medlem_rolle = discord.utils.get(interaction.user.roles, id=MEDLEM_ROLLE_ID)
        if not medlem_rolle:
            await interaction.response.send_message("⛔ Du skal have medlem rollen for at oprette opgaver!", ephemeral=True)
            return
        
        # Send modal
        await interaction.response.send_modal(OpretOpgaveModal())

class OpretOpgaveModal(Modal):
    def __init__(self):
        super().__init__(title="📝 Opret Ny Opgave")
        
        self.opgave_titel = TextInput(
            label="Opgave Titel",
            placeholder="F.eks. 'Hjælp til bank røveri'",
            required=True,
            max_length=100
        )
        
        self.opgave_beskrivelse = TextInput(
            label="Beskrivelse",
            placeholder="Beskriv hvad du har brug for hjælp til...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        
        self.belonning = TextInput(
            label="Belønning (valgfri)",
            placeholder="F.eks. '50k DKK' eller 'Del af profit'",
            required=False,
            max_length=100
        )
        
        self.add_item(self.opgave_titel)
        self.add_item(self.opgave_beskrivelse)
        self.add_item(self.belonning)

    async def on_submit(self, interaction: discord.Interaction):
        # Get next job counter from database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'job_counter'")
        job_counter = int(cursor.fetchone()[0])
        job_id = f"job_{job_counter}"
        conn.close()
        
        ny_opgave = {
            "id": job_id,
            "titel": self.opgave_titel.value,
            "beskrivelse": self.opgave_beskrivelse.value,
            "belonning": self.belonning.value if self.belonning.value else "Ikke angivet",
            "oprettet_af": interaction.user.id,
            "oprettet_navn": interaction.user.display_name
        }
        
        if add_member_job(ny_opgave):
            await interaction.response.send_message("✅ Din opgave er blevet oprettet og sendt til pusherne!", ephemeral=True)
            
            # Opdater pusher kanal
            pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
            if pusher_kanal:
                await update_pusher_embed(pusher_kanal)
        else:
            await interaction.response.send_message("⛔ Fejl ved oprettelse af opgave!", ephemeral=True)

async def send_pusher_embed(kanal):
    """Send pusher embed med alle jobs"""
    embed = discord.Embed(
        title="🎯 Vagos Pusher System",
        description="**Oversigt over alle tilgængelige jobs og opgaver**",
        color=0xFFD700  # Guld farve
    )
    
    # Permanente opgaver
    permanent_jobs = get_permanent_jobs()
    permanent_text = "\n".join([f"• {job}" for job in permanent_jobs])
    
    # Permanent jobs embed
    perm_embed = discord.Embed(
        title="🔄 Permanente Opgaver",
        description=f"```\n{permanent_text}\n```",
        color=0x5865F2
    )
    
    embed.add_field(
        name="🔄 Permanente Opgaver",
        value="Se separat embed nedenfor",
        inline=False
    )
    
    # Medlems opgaver med nummerering
    member_jobs = get_member_jobs()
    if member_jobs:
        member_jobs_text = ""
        for job in member_jobs:
            status_emoji = "🟢" if job["status"] == "ledig" else "🔴"
            job_number = job.get("job_number", "?")
            member_jobs_text += f"**#{job_number}** {status_emoji} **{job['titel']}**\n"
            member_jobs_text += f"       📝 {job['beskrivelse'][:50]}{'...' if len(job['beskrivelse']) > 50 else ''}\n"
            member_jobs_text += f"       💰 {job['belonning']}\n"
            member_jobs_text += f"       👤 Af: {job['oprettet_navn']}\n"
            if job["status"] == "optaget":
                member_jobs_text += f"       🎯 Pusher: {job['pusher_navn']}\n"
            member_jobs_text += "\n"
        
        # Member jobs embed  
        member_embed = discord.Embed(
            title="📋 Medlems Opgaver",
            description=member_jobs_text,
            color=0x57F287
        )
        
        embed.add_field(
            name="📋 Medlems Opgaver",
            value="Se separat embed nedenfor",
            inline=False
        )
    else:
        embed.add_field(
            name="📋 Medlems Opgaver",
            value="```\nIngen opgaver lige nu\n```",
            inline=False
        )
    
    embed.add_field(
        name="ℹ️ Information",
        value="Tryk på nummerknapperne nedenfor for at tage en opgave. Du får adgang til en privat kanal med medlemmet.",
        inline=False
    )
    
    embed.set_footer(text="Vagos Pusher System v1.0")
    embed.timestamp = datetime.now()
    
    # Send main embed
    await kanal.send(embed=embed)
    
    # Send permanent jobs embed
    await kanal.send(embed=perm_embed)
    
    # Send member jobs embed if any exist
    if member_jobs:
        await kanal.send(embed=member_embed)
    
    # Send buttons
    view = await create_job_buttons_view()
    if view.children:  # Only send if there are buttons
        await kanal.send("**Tryk på nummer for at tage job:**", view=view)

async def update_pusher_embed(kanal):
    """Opdater pusher embed"""
    # Slet gamle beskeder og send ny
    try:
        await kanal.purge()
        await send_pusher_embed(kanal)
    except Exception as e:
        print(f"Fejl ved opdatering af pusher embed: {e}")

async def create_job_buttons_view():
    """Opret view med nummerknapper for alle ledige jobs"""
    view = View(timeout=None)
    
    # Tilføj knapper for medlems opgaver
    member_jobs = get_member_jobs()
    for job in member_jobs:
        if job["status"] == "ledig":
            job_number = job.get("job_number", "?")
            button = Button(
                label=f"#{job_number}",
                style=discord.ButtonStyle.success,
                custom_id=f"take_job_{job['id']}"
            )
            view.add_item(button)
    
    return view

async def send_medlem_embed(kanal):
    """Send medlem embed med knap til at oprette opgaver"""
    embed = discord.Embed(
        title="📝 Opret Pusher Opgave",
        description="**Har du brug for hjælp fra vores pusherne?**",
        color=0x5865F2  # Discord blå
    )
    
    embed.add_field(
        name="🎯 Sådan fungerer det",
        value=(
            "1️⃣ Tryk på knappen nedenfor\n"
            "2️⃣ Udfyld formularen med din opgave\n"
            "3️⃣ En pusher vil tage dit job\n"
            "4️⃣ I får en privat kanal til at snakke sammen"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value=(
            "• Vær specifik i din beskrivelse\n"
            "• Angiv belønning hvis relevant\n"
            "• Vær klar til at svare når en pusher tager jobbet"
        ),
        inline=False
    )
    
    embed.set_footer(text="Vagos Pusher System v1.0")
    
    view = MedlemView()
    await kanal.send(embed=embed, view=view)

async def setup_pusher_stats_kanal():
    """Setup pusher statistik kanal"""
    kanal = bot.get_channel(PUSHER_STATS_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Pusher stats kanal med ID {PUSHER_STATS_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Clear channel
        await kanal.purge()
        print(f"🧹 Pusher stats kanal {kanal.name} er ryddet.")
    except Exception as e:
        print(f"❌ Fejl under rydning af pusher stats kanal: {e}")
    
    # Send stats embed
    await send_pusher_stats_embed(kanal)

def get_pusher_stats():
    """Get pusher statistics from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pusher_id, pusher_navn, total_jobs 
            FROM pusher_stats 
            ORDER BY total_jobs DESC
        """)
        stats = cursor.fetchall()
        conn.close()
        return stats
    except Exception as e:
        print(f"Fejl ved hentning af pusher stats: {e}")
        return []

def get_recent_completed_jobs(limit=5):
    """Get recent completed jobs from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT titel, pusher_navn, completed_tid, job_number
            FROM completed_jobs 
            ORDER BY completed_tid DESC 
            LIMIT ?
        """, (limit,))
        jobs = cursor.fetchall()
        conn.close()
        return jobs
    except Exception as e:
        print(f"Fejl ved hentning af seneste jobs: {e}")
        return []

async def send_pusher_stats_embed(kanal):
    """Send pusher statistik embed"""
    embed = discord.Embed(
        title="📊 Pusher Statistikker",
        description="**Oversigt over alle pusherne og deres færdiggjorte jobs**",
        color=0x00FF00
    )
    
    # Get pusher stats from database
    pusher_stats = get_pusher_stats()
    
    if not pusher_stats:
        embed.add_field(
            name="📋 Status",
            value="```\nIngen færdiggjorte jobs endnu\n```",
            inline=False
        )
    else:
        # Create rankings embed
        rankings_text = ""
        for i, (pusher_id, pusher_navn, total_jobs) in enumerate(pusher_stats, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
            rankings_text += f"{medal} **{pusher_navn}**: {total_jobs} jobs\n"
        
        rankings_embed = discord.Embed(
            title="🏆 Pusher Rankings",
            description=rankings_text,
            color=0xFFD700
        )
        
        embed.add_field(
            name="🏆 Pusher Rankings",
            value="Se separat embed nedenfor",
            inline=False
        )
    
    # Recent completed jobs
    recent_jobs = get_recent_completed_jobs(5)
    if recent_jobs:
        recent_text = ""
        for titel, pusher_navn, completed_tid, job_number in recent_jobs:
            date_str = completed_tid[:10] if completed_tid else "?"
            recent_text += f"✅ **#{job_number} {titel}**\n"
            recent_text += f"    🎯 {pusher_navn} ({date_str})\n\n"
        
        recent_embed = discord.Embed(
            title="🕒 Seneste Færdiggjorte Jobs",
            description=recent_text,
            color=0x57F287
        )
        
        embed.add_field(
            name="🕒 Seneste Færdiggjorte Jobs", 
            value="Se separat embed nedenfor",
            inline=False
        )
    else:
        embed.add_field(
            name="🕒 Seneste Færdiggjorte Jobs",
            value="```\nIngen endnu\n```",
            inline=False
        )
    
    embed.set_footer(text="Vagos Pusher Stats v1.0")
    embed.timestamp = datetime.now()
    
    # Send main embed
    await kanal.send(embed=embed)
    
    # Send rankings embed if exists
    if pusher_stats:
        await kanal.send(embed=rankings_embed)
    
    # Send recent jobs embed if exists
    if recent_jobs:
        await kanal.send(embed=recent_embed)

class JobControlView(View):
    def __init__(self, job_id):
        super().__init__(timeout=None)
        self.job_id = job_id

    @discord.ui.button(label="❌ Cancel Job", style=discord.ButtonStyle.danger)
    async def cancel_job(self, interaction: discord.Interaction, button: Button):
        # Find jobbet
        job = get_member_job_by_id(self.job_id)
        
        if not job:
            await interaction.response.send_message("⛔ Dette job eksisterer ikke længere!", ephemeral=True)
            return
        
        # Tjek om brugeren er medlem eller pusher på jobbet
        if interaction.user.id not in [job["oprettet_af"], job.get("pusher_id")]:
            await interaction.response.send_message("⛔ Du kan kun cancellere jobs du er involveret i!", ephemeral=True)
            return
        
        # Cancel jobbet
        if update_member_job_status(self.job_id, "ledig"):
            await interaction.response.send_message("✅ Jobbet er blevet cancelled og er nu ledigt igen!", ephemeral=False)
            
            # Opdater pusher kanal
            pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
            if pusher_kanal:
                await update_pusher_embed(pusher_kanal)
            
            # Slet den private kanal efter 10 sekunder
            await asyncio.sleep(10)
            try:
                await interaction.channel.delete()
            except:
                pass
        else:
            await interaction.response.send_message("⛔ Fejl ved cancellation af job!", ephemeral=True)

    @discord.ui.button(label="✅ Job Færdigt", style=discord.ButtonStyle.success)
    async def complete_job(self, interaction: discord.Interaction, button: Button):
        # Find jobbet
        job = get_member_job_by_id(self.job_id)
        
        if not job:
            await interaction.response.send_message("⛔ Dette job eksisterer ikke længere!", ephemeral=True)
            return
        
        # Tjek om brugeren er pusher på jobbet
        if interaction.user.id != job.get("pusher_id"):
            await interaction.response.send_message("⛔ Kun pusheren kan markere jobbet som færdigt!", ephemeral=True)
            return
        
        # Marker job som færdigt
        if complete_member_job(self.job_id):
            await interaction.response.send_message("🎉 Jobbet er markeret som færdigt! Godt arbejde!", ephemeral=False)
            
            # Opdater pusher kanal og stats
            pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
            if pusher_kanal:
                await update_pusher_embed(pusher_kanal)
            
            stats_kanal = bot.get_channel(PUSHER_STATS_KANAL_ID)
            if stats_kanal:
                await update_pusher_stats_embed(stats_kanal)
            
            # Slet den private kanal efter 10 sekunder
            await asyncio.sleep(10)
            try:
                await interaction.channel.delete()
            except:
                pass
        else:
            await interaction.response.send_message("⛔ Fejl ved færdiggørelse af job!", ephemeral=True)

async def update_pusher_stats_embed(kanal):
    """Opdater pusher stats embed"""
    try:
        await kanal.purge()
        await send_pusher_stats_embed(kanal)
    except Exception as e:
        print(f"Fejl ved opdatering af pusher stats embed: {e}")

@bot.event
async def on_interaction(interaction):
    """Handle button interactions"""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id.startswith("take_job_"):
            await handle_take_job(interaction, custom_id)

async def handle_take_job(interaction, custom_id):
    """Handle når en pusher tager et job"""
    job_id = custom_id.replace("take_job_", "")
    
    # Find jobbet
    job = get_member_job_by_id(job_id)
    
    if not job:
        await interaction.response.send_message("⛔ Dette job eksisterer ikke længere!", ephemeral=True)
        return
    
    if job["status"] == "optaget":
        await interaction.response.send_message("⛔ Dette job er allerede taget!", ephemeral=True)
        return
    
    # Marker job som optaget
    if not update_member_job_status(job_id, "optaget", interaction.user.id, interaction.user.display_name):
        await interaction.response.send_message("⛔ Fejl ved tildeling af job!", ephemeral=True)
        return
    
    # Opret privat kanal
    try:
        guild = interaction.guild
        kategori = discord.utils.get(guild.categories, id=PRIVAT_KATEGORI_ID)
        
        if not kategori:
            await interaction.response.send_message("⛔ Kunne ikke finde kategorien til private kanaler!", ephemeral=True)
            return
        
        # Hent medlem og pusher
        medlem = await bot.fetch_user(job["oprettet_af"])
        pusher = interaction.user
        
        # Opret kanal navn
        kanal_navn = f"job-{job['id']}-{medlem.display_name[:10]}"
        
        # Opret kanalen
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            medlem: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            pusher: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        privat_kanal = await kategori.create_text_channel(
            name=kanal_navn,
            overwrites=overwrites
        )
        
        # Send besked i den private kanal
        job_embed = discord.Embed(
            title="🤝 Job Match!",
            description=f"**{pusher.display_name}** har taget jobbet fra **{medlem.display_name}**",
            color=0x00FF00
        )
        
        job_embed.add_field(
            name="📋 Opgave",
            value=f"**{job['titel']}**\n{job['beskrivelse']}",
            inline=False
        )
        
        job_embed.add_field(
            name="💰 Belønning",
            value=job['belonning'],
            inline=True
        )
        
        job_embed.add_field(
            name="📅 Oprettet",
            value=job['oprettet_tid'][:16].replace('T', ' '),
            inline=True
        )
        
        job_embed.set_footer(text="I kan nu koordinere jeres samarbejde her!")
        
        # Tilføj job kontrol knapper
        control_view = JobControlView(job_id)
        
        await privat_kanal.send(f"{medlem.mention} {pusher.mention}", embed=job_embed, view=control_view)
        
        # Gem kanal ID til jobbet
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE member_jobs SET privat_kanal_id = ? WHERE id = ?", (privat_kanal.id, job_id))
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"✅ Du har taget jobbet! Privat kanal oprettet: {privat_kanal.mention}", ephemeral=True)
        
        # Opdater pusher kanal
        pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
        if pusher_kanal:
            await update_pusher_embed(pusher_kanal)
            
    except Exception as e:
        print(f"Fejl ved oprettelse af privat kanal: {e}")
        await interaction.response.send_message("⛔ Fejl ved oprettelse af privat kanal!", ephemeral=True)

class AddPermOpgaveModal(Modal):
    def __init__(self):
        super().__init__(title="➕ Tilføj Permanent Opgave")
        
        self.opgave_tekst = TextInput(
            label="Opgave Tekst",
            placeholder="F.eks. '🎲 Hjælpe med casino heists'",
            required=True,
            max_length=100
        )
        
        self.add_item(self.opgave_tekst)

    async def on_submit(self, interaction: discord.Interaction):
        ny_opgave = self.opgave_tekst.value
        
        if add_permanent_job(ny_opgave):
            await interaction.response.send_message(f"✅ Permanent opgave tilføjet: {ny_opgave}", ephemeral=True)
            
            # Opdater pusher kanal
            pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
            if pusher_kanal:
                await update_pusher_embed(pusher_kanal)
        else:
            await interaction.response.send_message("⛔ Denne opgave eksisterer allerede eller fejl ved tilføjelse!", ephemeral=True)

class EditPermOpgaveModal(Modal):
    def __init__(self, gammel_opgave):
        super().__init__(title="✏️ Rediger Permanent Opgave")
        self.gammel_opgave = gammel_opgave
        
        self.opgave_tekst = TextInput(
            label="Opgave Tekst",
            default=gammel_opgave,
            required=True,
            max_length=100
        )
        
        self.add_item(self.opgave_tekst)

    async def on_submit(self, interaction: discord.Interaction):
        ny_tekst = self.opgave_tekst.value
        
        if update_permanent_job(self.gammel_opgave, ny_tekst):
            await interaction.response.send_message(f"✅ Opgave opdateret:\n**Fra:** {self.gammel_opgave}\n**Til:** {ny_tekst}", ephemeral=True)
            
            # Opdater pusher kanal
            pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
            if pusher_kanal:
                await update_pusher_embed(pusher_kanal)
        else:
            await interaction.response.send_message("⛔ Fejl ved opdatering af opgave!", ephemeral=True)

class RemovePermOpgaveSelect(Select):
    def __init__(self):
        options = []
        permanent_jobs = get_permanent_jobs()
        for opgave in permanent_jobs:
            # Begræns længden af opgave teksten til select menu
            display_text = opgave[:50] + "..." if len(opgave) > 50 else opgave
            options.append(discord.SelectOption(
                label=display_text,
                value=opgave,
                description=f"Fjern denne opgave"
            ))
        
        super().__init__(placeholder="Vælg opgave at fjerne...", options=options, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        opgave_to_remove = self.values[0]
        
        if remove_permanent_job(opgave_to_remove):
            await interaction.response.send_message(f"✅ Permanent opgave fjernet: {opgave_to_remove}", ephemeral=True)
            
            # Opdater pusher kanal
            pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
            if pusher_kanal:
                await update_pusher_embed(pusher_kanal)
        else:
            await interaction.response.send_message("⛔ Fejl ved fjernelse af opgave!", ephemeral=True)

class EditPermOpgaveSelect(Select):
    def __init__(self):
        options = []
        permanent_jobs = get_permanent_jobs()
        for opgave in permanent_jobs:
            # Begræns længden af opgave teksten til select menu
            display_text = opgave[:50] + "..." if len(opgave) > 50 else opgave
            options.append(discord.SelectOption(
                label=display_text,
                value=opgave,
                description=f"Rediger denne opgave"
            ))
        
        super().__init__(placeholder="Vælg opgave at redigere...", options=options, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        gammel_opgave = self.values[0]
        
        # Send modal
        await interaction.response.send_modal(EditPermOpgaveModal(gammel_opgave))

def tjek_admin_rolle(user):
    """Tjek om brugeren har admin rollen"""
    return any(role.id == ADMIN_ROLLE_ID for role in user.roles)

@bot.command(name="pusherbot")
async def pusherbot_admin(ctx, action=None, subaction=None):
    """Admin kommandoer til pusher bot"""
    
    # Tjek admin rolle
    if not tjek_admin_rolle(ctx.author):
        await ctx.send("⛔ Du har ikke tilladelse til at bruge admin kommandoer!")
        return
    
    if action is None:
        embed = discord.Embed(
            title="🔧 Pusher Bot Admin",
            description="**Tilgængelige kommandoer:**",
            color=0xFF5733
        )
        embed.add_field(
            name="📝 Permanent Opgaver",
            value=(
                "`!pusherbot permopg add` - Tilføj ny permanent opgave\n"
                "`!pusherbot permopg edit` - Rediger eksisterende opgave\n"
                "`!pusherbot permopg remove` - Fjern permanent opgave"
            ),
            inline=False
        )
        embed.set_footer(text="Kun administratorer kan bruge disse kommandoer")
        await ctx.send(embed=embed)
        return
    
    if action.lower() != "permopg":
        await ctx.send("⛔ Ukendt kommando! Brug `!pusherbot permopg [add/edit/remove]`")
        return
    
    if subaction is None:
        embed = discord.Embed(
            title="🔧 Permanent Opgave Admin",
            description="**Brug:** `!pusherbot permopg [add/edit/remove]`",
            color=0xFF5733
        )
        embed.add_field(
            name="📝 Kommandoer",
            value=(
                "`add` - Tilføj ny permanent opgave\n"
                "`edit` - Rediger eksisterende opgave\n"
                "`remove` - Fjern permanent opgave"
            ),
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    if subaction.lower() == "add":
        # Send modal for at tilføje ny opgave
        view = View()
        button = Button(label="➕ Tilføj Opgave", style=discord.ButtonStyle.primary)
        
        async def add_callback(interaction):
            await interaction.response.send_modal(AddPermOpgaveModal())
        
        button.callback = add_callback
        view.add_item(button)
        
        await ctx.send("Tryk på knappen for at tilføje en ny permanent opgave:", view=view)
    
    elif subaction.lower() == "edit":
        permanent_jobs = get_permanent_jobs()
        if not permanent_jobs:
            await ctx.send("⛔ Ingen permanente opgaver at redigere!")
            return
        
        view = View()
        view.add_item(EditPermOpgaveSelect())
        await ctx.send("Vælg opgave at redigere:", view=view)
    
    elif subaction.lower() == "remove":
        permanent_jobs = get_permanent_jobs()
        if not permanent_jobs:
            await ctx.send("⛔ Ingen permanente opgaver at fjerne!")
            return
        
        view = View()
        view.add_item(RemovePermOpgaveSelect())
        await ctx.send("Vælg opgave at fjerne:", view=view)
    
    else:
        await ctx.send("⛔ Ukendt subkommando! Brug `add`, `edit`, eller `remove`")

@bot.command()
async def admin_reset(ctx):
    """Reset alle jobs (kun til admin)"""
    if not tjek_admin_rolle(ctx.author):
        await ctx.send("⛔ Du har ikke tilladelse til at nulstille systemet!")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Clear all tables except permanent_jobs
        cursor.execute("DELETE FROM member_jobs")
        cursor.execute("DELETE FROM completed_jobs")
        cursor.execute("DELETE FROM pusher_stats")
        cursor.execute("UPDATE settings SET value = '1' WHERE key = 'job_counter'")
        
        conn.commit()
        conn.close()
        
        # Opdater kanaler
        await setup_pusher_kanal()
        await setup_medlem_kanal()
        await setup_pusher_stats_kanal()
        
        await ctx.send("✅ Alle jobs og statistikker er blevet nulstillet!")
        
    except Exception as e:
        await ctx.send(f"⛔ Fejl ved nulstilling: {e}")
        print(f"Fejl ved admin reset: {e}")

bot.run(TOKEN)

