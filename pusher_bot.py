import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
from datetime import datetime, timedelta
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
intents.members = True  # Nødvendigt for member events

bot = commands.Bot(command_prefix="!", intents=intents)

# Kanal og rolle IDs
FULDT_MEDLEM_ROLLE_ID = 1367567899828686891
ADMIN_ROLLE_IDS = [1367567899878883413]
ABSOLUT_ADMIN_ID = 356831538916098048
DEV_ROLLE_ID = 1439336949331529994  # Dev rolle - bypasser alle checks
SUPPORTER_ROLLE_ID = 1387100355535437917
PROSPECT_ROLLE_ID = 1386720142196736061
PROSPECT_SUPPORTER_ROLLE_IDS = [SUPPORTER_ROLLE_ID, PROSPECT_ROLLE_ID]

# Logo URL
LOGO_URL = "https://cdn.discordapp.com/attachments/1439332163131674755/1439332204332318980/image.png?ex=691a2213&is=6918d093&hm=9e1217edfdd03d0f39516fc5617acd8585be87f54e7939845661cd14879ff8eb&"

# Kanaler
OPGAVE_KANAL_ID = 1439329928679129211
OPGAVE_OPRETTELSES_KANAL_ID = 1439330014838522159
STATUS_KANAL_ID = 1439329956327981206
ADMIN_PANEL_KANAL_ID = 1439585440016367795
PRIVAT_KATEGORI_ID = 1439340235820499036

# Gamle prospect_supporter konstanter (for reference - kan fjernes senere)
# OPGAVE_KANAL_ID = 1427388722709663895
# OPGAVE_OPRETTELSES_KANAL_ID = 1427421512637349948
# PUSHER_STATS_KANAL_ID = 1427388707807297556
# PROSPECT_SUPPORTER_ROLLE_IDS[0] = 1430353400385507448
# MARKBETALINGS_KANAL_ID = 1434546263528968273  # Disabled

# Database setup
DATA_DIR = Path("/data") if Path("/data").exists() else Path(".")
DB_PATH = DATA_DIR / "prospect_supporter_bot.db"

# Default permanent jobs
DEFAULT_PERMANENT_JOBS = [

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
                point_reward INTEGER DEFAULT 0,
                oprettet_af INTEGER NOT NULL,
                oprettet_navn TEXT NOT NULL,
                status TEXT DEFAULT 'ledig',
                prospect_supporter_id INTEGER,
                prospect_supporter_navn TEXT,
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
                point_reward INTEGER DEFAULT 0,
                oprettet_af INTEGER NOT NULL,
                oprettet_navn TEXT NOT NULL,
                prospect_supporter_id INTEGER NOT NULL,
                prospect_supporter_navn TEXT NOT NULL,
                completed_tid TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                job_number INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prospect_supporter_stats (
                prospect_supporter_id INTEGER PRIMARY KEY,
                prospect_supporter_navn TEXT NOT NULL,
                total_points INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migration: Omdøb gamle prospect_supporter_stats hvis den eksisterer
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='prospect_supporter_stats'
        ''')
        if cursor.fetchone():
            # Check om total_points kolonne eksisterer
            cursor.execute('PRAGMA table_info(prospect_supporter_stats)')
            columns = [col[1] for col in cursor.fetchall()]
            if 'total_points' not in columns:
                try:
                    cursor.execute('ALTER TABLE prospect_supporter_stats RENAME TO prospect_supporter_stats_old')
                    cursor.execute('ALTER TABLE prospect_supporter_stats RENAME TO prospect_supporter_stats_backup')
                except:
                    pass
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # Disabled: Markbetalinger
        # cursor.execute('''
        #     CREATE TABLE IF NOT EXISTS markbetalinger (
        #         id INTEGER PRIMARY KEY AUTOINCREMENT,
        #         navn TEXT NOT NULL,
        #         telefon TEXT NOT NULL,
        #         tidsperiode TEXT NOT NULL,
        #         betalingsdato TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #         udlobsdato TIMESTAMP,
        #         oprettet_af INTEGER NOT NULL,
        #         oprettet_navn TEXT NOT NULL
        #     )
        # ''')
        
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
            SELECT id, titel, beskrivelse, belonning, point_reward, oprettet_af, oprettet_navn, 
                   status, prospect_supporter_id, prospect_supporter_navn, privat_kanal_id, oprettet_tid, 
                   taget_tid, job_number
            FROM member_jobs 
            ORDER BY job_number
        """)
        jobs = []
        for row in cursor.fetchall():
            job = {
                "id": row[0], "titel": row[1], "beskrivelse": row[2], "belonning": row[3],
                "point_reward": row[4] if len(row) > 4 else 0, "oprettet_af": row[5], "oprettet_navn": row[6], 
                "status": row[7], "prospect_supporter_id": row[8], "prospect_supporter_navn": row[9], 
                "privat_kanal_id": row[10], "oprettet_tid": row[11], "taget_tid": row[12], 
                "job_number": row[13]
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
            (id, titel, beskrivelse, belonning, point_reward, oprettet_af, oprettet_navn, job_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_data["id"], job_data["titel"], job_data["beskrivelse"],
            job_data["belonning"], job_data.get("point_reward", 0), 
            job_data["oprettet_af"], job_data["oprettet_navn"],
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

def update_member_job_status(job_id, status, prospect_supporter_id=None, prospect_supporter_navn=None):
    """Update member job status in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if prospect_supporter_id and prospect_supporter_navn:
            cursor.execute("""
                UPDATE member_jobs 
                SET status = ?, prospect_supporter_id = ?, prospect_supporter_navn = ?, taget_tid = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, prospect_supporter_id, prospect_supporter_navn, job_id))
        else:
            cursor.execute("UPDATE member_jobs SET status = ? WHERE id = ?", (status, job_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"Fejl ved opdatering af job status: {e}")
        return False

def update_private_channel_id(job_id, channel_id):
    """Update private channel ID for a job"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE member_jobs SET privat_kanal_id = ? WHERE id = ?", (channel_id, job_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"Fejl ved opdatering af kanal ID: {e}")
        return False

def get_all_active_private_channels():
    """Get all active private channel IDs from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT privat_kanal_id, id FROM member_jobs WHERE privat_kanal_id IS NOT NULL AND status = 'optaget'")
        channels = cursor.fetchall()
        conn.close()
        return channels
    except Exception as e:
        print(f"Fejl ved hentning af private kanaler: {e}")
        return []

def complete_member_job(job_id):
    """Complete a member job and update stats (bruges til legacy/fallback)"""
    return complete_member_job_with_points(job_id, 0)

def complete_member_job_with_points(job_id, point_reward):
    """Complete a member job and update stats with specified point reward"""
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
            (id, titel, beskrivelse, belonning, point_reward, oprettet_af, oprettet_navn, 
             prospect_supporter_id, prospect_supporter_navn, job_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_row[0], job_row[1], job_row[2], job_row[3], point_reward, job_row[5], 
              job_row[6], job_row[8], job_row[9], job_row[13]))
        
        # Update prospect_supporter stats with points
        cursor.execute("""
            INSERT OR REPLACE INTO prospect_supporter_stats (prospect_supporter_id, prospect_supporter_navn, total_points)
            VALUES (?, ?, COALESCE((SELECT total_points FROM prospect_supporter_stats WHERE prospect_supporter_id = ?), 0) + ?)
        """, (job_row[8], job_row[9], job_row[8], point_reward))
        
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
                   status, prospect_supporter_id, prospect_supporter_navn, privat_kanal_id, oprettet_tid, 
                   taget_tid, job_number
            FROM member_jobs WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0], "titel": row[1], "beskrivelse": row[2], "belonning": row[3],
                "oprettet_af": row[4], "oprettet_navn": row[5], "status": row[6],
                "prospect_supporter_id": row[7], "prospect_supporter_navn": row[8], "privat_kanal_id": row[9],
                "oprettet_tid": row[10], "taget_tid": row[11], "job_number": row[12]
            }
        return None
    except Exception as e:
        print(f"Fejl ved hentning af job: {e}")
        return None

def get_member_job_by_number(job_number):
    """Get specific member job by job number"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titel, beskrivelse, belonning, oprettet_af, oprettet_navn, 
                   status, prospect_supporter_id, prospect_supporter_navn, privat_kanal_id, oprettet_tid, 
                   taget_tid, job_number
            FROM member_jobs WHERE job_number = ?
        """, (job_number,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0], "titel": row[1], "beskrivelse": row[2], "belonning": row[3],
                "oprettet_af": row[4], "oprettet_navn": row[5], "status": row[6],
                "prospect_supporter_id": row[7], "prospect_supporter_navn": row[8], "privat_kanal_id": row[9],
                "oprettet_tid": row[10], "taget_tid": row[11], "job_number": row[12]
            }
        return None
    except Exception as e:
        print(f"Fejl ved hentning af job: {e}")
        return None

def delete_member_job_by_id(job_id):
    """Delete a member job by ID and close its private channel if exists"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get job info before deleting
        cursor.execute("SELECT privat_kanal_id FROM member_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        privat_kanal_id = row[0] if row else None
        
        # Delete the job
        cursor.execute("DELETE FROM member_jobs WHERE id = ?", (job_id,))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success, privat_kanal_id
    except Exception as e:
        print(f"Fejl ved sletning af job: {e}")
        return False, None

# Disabled: Markbetalinger
# def get_markbetalinger():
    """Get all markbetalinger from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, navn, telefon, tidsperiode, betalingsdato, udlobsdato, 
                   oprettet_af, oprettet_navn
            FROM markbetalinger 
            ORDER BY betalingsdato DESC
        """)
        betalinger = []
        for row in cursor.fetchall():
            betaling = {
                "id": row[0], "navn": row[1], "telefon": row[2], 
                "tidsperiode": row[3], "betalingsdato": row[4], 
                "udlobsdato": row[5], "oprettet_af": row[6], 
                "oprettet_navn": row[7]
            }
            betalinger.append(betaling)
        conn.close()
        return betalinger
    except Exception as e:
        print(f"Fejl ved hentning af markbetalinger: {e}")
        return []

# def add_markbetaling(betaling_data):
    """Add markbetaling to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Beregn udløbsdato baseret på tidsperiode
        betalingsdato = datetime.now()
        tidsperiode = betaling_data["tidsperiode"]
        
        if tidsperiode == "24 timer":
            udlobsdato = betalingsdato + timedelta(days=1)
        elif tidsperiode == "3 døgn":
            udlobsdato = betalingsdato + timedelta(days=3)
        elif tidsperiode == "1 uge":
            udlobsdato = betalingsdato + timedelta(days=7)
        else:
            udlobsdato = betalingsdato + timedelta(days=1)  # Default
        
        cursor.execute("""
            INSERT INTO markbetalinger 
            (navn, telefon, tidsperiode, betalingsdato, udlobsdato, oprettet_af, oprettet_navn)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            betaling_data["navn"], 
            betaling_data["telefon"],
            betaling_data["tidsperiode"],
            betalingsdato.strftime("%Y-%m-%d %H:%M:%S"),
            udlobsdato.strftime("%Y-%m-%d %H:%M:%S"),
            betaling_data["oprettet_af"],
            betaling_data["oprettet_navn"]
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Fejl ved tilføjelse af markbetaling: {e}")
        return False

@bot.event
async def on_ready():
    print(f"Prospect/Supporter Bot er online som {bot.user}")
    
    # Set bot avatar/logo
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(LOGO_URL) as response:
                if response.status == 200:
                    avatar_data = await response.read()
                    await bot.user.edit(avatar=avatar_data)
                    print("✅ Bot avatar opdateret med Red Devils logo")
                else:
                    print("⚠️ Kunne ikke hente logo til bot avatar")
    except Exception as e:
        print(f"⚠️ Fejl ved opdatering af bot avatar: {e}")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
    
    # Initialize database
    init_database()
    
    # Setup kanaler
    await setup_prospect_supporter_kanal()
    await setup_opgave_oprettelse_kanal()
    await setup_prospect_supporter_stats_kanal()
    await setup_admin_panel_kanal()
    # await setup_markbetalinger_kanal()  # Disabled
    
    # Start periodisk check som backup
    periodic_stats_check.start()

@bot.event
async def on_member_update(before, after):
    """Opdater prospect_supporter stats når medlemmer får/mister prospect_supporter rollen"""
    try:
        # Debug: Log alle rolle ændringer
        print(f"🔍 Member update detected for {after.display_name}")
        
        # Tjek om prospect_supporter rollen er ændret
        before_has_role = any(role.id in PROSPECT_SUPPORTER_ROLLE_IDS for role in before.roles)
        after_has_role = any(role.id in PROSPECT_SUPPORTER_ROLLE_IDS for role in after.roles)
        
        print(f"🔍 Prospect/Supporter rolle check: {before_has_role} → {after_has_role}")
        
        # Hvis prospect_supporter rollen er ændret
        if before_has_role != after_has_role:
            print(f"🔄 PUSHER ROLLE ÆNDRET for {after.display_name}: {before_has_role} → {after_has_role}")
            
            # Vent lidt for at sikre Discord har opdateret
            await asyncio.sleep(2)
            
            # Opdater stats kanal automatisk
            stats_kanal = bot.get_channel(STATUS_KANAL_ID)
            if stats_kanal:
                await update_prospect_supporter_stats_embed(stats_kanal)
                print(f"✅ OPDATEREDE prospect_supporter stats efter rolle ændring for {after.display_name}")
            else:
                print(f"⚠️ Stats kanal ikke fundet!")
    except Exception as e:
        print(f"❌ Fejl i on_member_update: {e}")

@bot.event
async def on_member_remove(member):
    """Opdater prospect_supporter stats når et medlem forlader serveren"""
    # Tjek om medlemmet havde prospect_supporter rollen
    had_prospect_supporter_role = any(role.id in PROSPECT_SUPPORTER_ROLLE_IDS for role in member.roles)
    
    if had_prospect_supporter_role:
        print(f"👋 Prospect/Supporter {member.display_name} forlod serveren")
        
        # Opdater stats kanal automatisk
        stats_kanal = bot.get_channel(STATUS_KANAL_ID)
        if stats_kanal:
            # Vent lidt så Discord opdaterer rolle listen
            await asyncio.sleep(1)
            await update_prospect_supporter_stats_embed(stats_kanal)
            print(f"✅ Opdaterede prospect_supporter stats efter {member.display_name} forlod serveren")

@bot.event
async def on_member_join(member):
    """Potentielt opdater prospect_supporter stats hvis ny medlem får prospect_supporter rolle hurtigt"""
    # Denne event trigger ikke stats opdatering med det samme,
    # men on_member_update vil fange det når de får rollen
    pass

async def setup_prospect_supporter_kanal():
    """Setup prospect_supporter kanal med job oversigt"""
    kanal = bot.get_channel(OPGAVE_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Prospect/Supporter kanal med ID {OPGAVE_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Clear channel
        await kanal.purge()
        print(f"🧹 Prospect/Supporter kanal {kanal.name} er ryddet.")
    except Exception as e:
        print(f"❌ Fejl under rydning af prospect_supporter kanal: {e}")
    
    # Send prospect_supporter embed
    await send_prospect_supporter_embed(kanal)

async def setup_opgave_oprettelse_kanal():
    """Setup opgave oprettelses kanal med knap til at oprette jobs"""
    kanal = bot.get_channel(OPGAVE_OPRETTELSES_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Opgave oprettelses kanal med ID {OPGAVE_OPRETTELSES_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Clear channel
        await kanal.purge()
        print(f"🧹 Medlem kanal {kanal.name} er ryddet.")
    except Exception as e:
        print(f"❌ Fejl under rydning af medlem kanal: {e}")
    
    # Send opgave oprettelse embed
    await send_opgave_oprettelse_embed(kanal)

class ProspectSupporterJobView(View):
    def __init__(self):
        super().__init__(timeout=None)

class MedlemView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ Opret Opgave", style=discord.ButtonStyle.primary, emoji="📝")
    async def opret_opgave(self, interaction: discord.Interaction, button: Button):
        # Tjek om brugeren har en af medlem rollerne
        if not tjek_medlem_rolle(interaction.user):
            await interaction.response.send_message("⛔ Du skal have medlem rollen for at oprette opgaver!", ephemeral=True)
            return
        
        # Send modal
        await interaction.response.send_modal(OpretOpgaveModal())

# Disabled: Markbetalinger
# class MarkbetalingView(View):
#     def __init__(self):
#         super().__init__(timeout=None)
# 
#     @discord.ui.button(label="➕ Tilføj Betaling", style=discord.ButtonStyle.primary, emoji="💳")
#     async def tilfoej_betaling(self, interaction: discord.Interaction, button: Button):
#         # Tjek om brugeren har en af medlem rollerne
#         if not tjek_medlem_rolle(interaction.user):
#             await interaction.response.send_message("⛔ Du skal have medlem rollen for at tilføje betalinger!", ephemeral=True)
#             return
#         
#         # Send modal med select menu for tidsperiode
#         view = View(timeout=None)
#         select = TidsperiodeSelect()
#         view.add_item(select)
#         
#         # Send view først, så brugeren kan vælge tidsperiode
#         await interaction.response.send_message(
#             "**Vælg tidsperiode:**",
#             view=view,
#             ephemeral=True
#         )
# 
# class TidsperiodeSelect(Select):
#     def __init__(self):
#         options = [
#             discord.SelectOption(
#                 label="24 timer",
#                 value="24 timer",
#                 description="Betaling gælder i 24 timer"
#             ),
#             discord.SelectOption(
#                 label="3 døgn",
#                 value="3 døgn",
#                 description="Betaling gælder i 3 døgn"
#             ),
#             discord.SelectOption(
#                 label="1 uge",
#                 value="1 uge",
#                 description="Betaling gælder i 1 uge"
#             )
#         ]
#         super().__init__(placeholder="Vælg tidsperiode...", options=options, max_values=1)
# 
#     async def callback(self, interaction: discord.Interaction):
#         # Send modal med navn og telefon
#         await interaction.response.send_modal(TilføjBetalingModal(self.values[0]))
# 
# class TilføjBetalingModal(Modal):
#     def __init__(self, tidsperiode):
#         super().__init__(title="💳 Tilføj Betaling")
#         self.tidsperiode = tidsperiode
#         
#         self.navn = TextInput(
#             label="Navn",
#             placeholder="Indtast navn på personen der har betalt...",
#             required=True,
#             max_length=100
#         )
#         
#         self.telefon = TextInput(
#             label="Telefonnummer",
#             placeholder="Indtast telefonnummer...",
#             required=True,
#             max_length=20
#         )
#         
#         self.add_item(self.navn)
#         self.add_item(self.telefon)
# 
#     async def on_submit(self, interaction: discord.Interaction):
#         betaling_data = {
#             "navn": self.navn.value,
#             "telefon": self.telefon.value,
#             "tidsperiode": self.tidsperiode,
#             "oprettet_af": interaction.user.id,
#             "oprettet_navn": interaction.user.display_name
#         }
#         
#         # Disabled: Markbetalinger
#         # if add_markbetaling(betaling_data):
#         #     await interaction.response.send_message("✅ Betaling er blevet tilføjet!", ephemeral=True)
#         #     
#         #     # Opdater markbetalinger kanal
#         #     kanal = bot.get_channel(MARKBETALINGS_KANAL_ID)
#         #     if kanal:
#         #         await update_markbetalinger_embed(kanal)
#         # else:
#         #     await interaction.response.send_message("⛔ Fejl ved tilføjelse af betaling!", ephemeral=True)
#         await interaction.response.send_message("⛔ Markbetalinger er deaktiveret!", ephemeral=True)

# Disabled: Markbetalinger
# async def update_markbetalinger_embed(kanal):
#     """Opdater markbetalinger embed"""
#     try:
#         # Hent alle beskeder i kanalen fra botten
#         messages = []
#         async for message in kanal.history(limit=50):
#             if message.author == bot.user and (message.embeds or message.components):
#                 messages.append(message)
#         
#         # Slet alle embed/component beskeder fra botten
#         for message in messages:
#             try:
#                 await message.delete()
#             except:
#                 pass
#         
#         # Send opdateret embed
#         await send_markbetalinger_embed(kanal)
#         
#     except Exception as e:
#         print(f"Fejl ved opdatering af markbetalinger embed: {e}")

class AdminControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ Tilføj Permanent Opgave", style=discord.ButtonStyle.primary, emoji="🔄")
    async def add_permanent_job(self, interaction: discord.Interaction, button: Button):
        if not tjek_admin_rolle(interaction.user):
            await interaction.response.send_message("⛔ Kun admins kan bruge denne funktion!", ephemeral=True)
            return
        
        await interaction.response.send_modal(AddPermOpgaveModal())

    @discord.ui.button(label="✏️ Rediger Permanent Opgave", style=discord.ButtonStyle.secondary, emoji="📝")
    async def edit_permanent_job(self, interaction: discord.Interaction, button: Button):
        if not tjek_admin_rolle(interaction.user):
            await interaction.response.send_message("⛔ Kun admins kan bruge denne funktion!", ephemeral=True)
            return
        
        permanent_jobs = get_permanent_jobs()
        if not permanent_jobs:
            await interaction.response.send_message("⛔ Ingen permanente opgaver at redigere!", ephemeral=True)
            return
        
        view = View()
        view.add_item(EditPermOpgaveSelect())
        await interaction.response.send_message("Vælg opgave at redigere:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ Fjern Permanent Opgave", style=discord.ButtonStyle.danger, emoji="❌")
    async def remove_permanent_job(self, interaction: discord.Interaction, button: Button):
        if not tjek_admin_rolle(interaction.user):
            await interaction.response.send_message("⛔ Kun admins kan bruge denne funktion!", ephemeral=True)
            return
        
        permanent_jobs = get_permanent_jobs()
        if not permanent_jobs:
            await interaction.response.send_message("⛔ Ingen permanente opgaver at fjerne!", ephemeral=True)
            return
        
        view = View()
        view.add_item(RemovePermOpgaveSelect())
        await interaction.response.send_message("Vælg opgave at fjerne:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ Slet Medlem Opgave", style=discord.ButtonStyle.danger, emoji="📋")
    async def delete_member_job(self, interaction: discord.Interaction, button: Button):
        if not tjek_admin_rolle(interaction.user):
            await interaction.response.send_message("⛔ Kun admins kan bruge denne funktion!", ephemeral=True)
            return
        
        # Send modal til at indtaste opgave nummer
        await interaction.response.send_modal(DeleteMemberJobModal())

    @discord.ui.button(label="⚠️ NULSTIL SYSTEM", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reset_system(self, interaction: discord.Interaction, button: Button):
        if not tjek_admin_rolle(interaction.user):
            await interaction.response.send_message("⛔ Kun admins kan bruge denne funktion!", ephemeral=True)
            return
        
        # Send bekræftelses modal
        await interaction.response.send_modal(ResetSystemModal())

class DeleteMemberJobModal(Modal):
    def __init__(self):
        super().__init__(title="🗑️ Slet Vigtig Opgave")
        
        self.job_number = TextInput(
            label="Opgave Nummer",
            placeholder="Indtast opgave nummeret...",
            required=True,
            max_length=10
        )
        
        self.add_item(self.job_number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            job_number = int(self.job_number.value)
        except ValueError:
            await interaction.response.send_message("⛔ Ugyldigt nummer! Indtast et gyldigt tal.", ephemeral=True)
            return
        
        # Find jobbet
        job = get_member_job_by_number(job_number)
        if not job:
            await interaction.response.send_message(f"⛔ Ingen opgave fundet med nummer **{job_number}**!", ephemeral=True)
            return
        
        # Slet jobbet
        success, privat_kanal_id = delete_member_job_by_id(job["id"])
        
        if success:
            # Luk privat kanal hvis den eksisterer (uden at sende besked)
            if privat_kanal_id:
                privat_kanal = bot.get_channel(privat_kanal_id)
                if privat_kanal:
                    try:
                        await asyncio.sleep(2)  # Kort pause før kanalen lukkes
                        await privat_kanal.delete()
                    except:
                        pass
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
            
            embed = discord.Embed(
                title="✅ Opgave Slettet",
                description=f"**Opgave #{job_number}** er blevet slettet",
                color=0x00FF00
            )
            embed.add_field(name="Titel", value=job["titel"], inline=False)
            embed.add_field(name="Oprettet af", value=job["oprettet_navn"], inline=True)
            embed.add_field(name="Status", value=job["status"], inline=True)
            embed.set_thumbnail(url=LOGO_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("⛔ Fejl ved sletning af opgave!", ephemeral=True)

class ResetSystemModal(Modal):
    def __init__(self):
        super().__init__(title="⚠️ NULSTIL SYSTEM")
        
        self.confirmation = TextInput(
            label="Bekræftelse",
            placeholder="Skriv 'NULSTIL' for at bekræfte...",
            required=True,
            max_length=10
        )
        
        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation.value.upper() != "NULSTIL":
            await interaction.response.send_message("⛔ Bekræftelse fejlede! Skriv 'NULSTIL' for at bekræfte.", ephemeral=True)
            return
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Clear all tables except permanent_jobs
            cursor.execute("DELETE FROM member_jobs")
            cursor.execute("DELETE FROM completed_jobs")
            cursor.execute("DELETE FROM prospect_supporter_stats")
            cursor.execute("UPDATE settings SET value = '1' WHERE key = 'job_counter'")
            
            conn.commit()
            conn.close()
            
            # Opdater kanaler
            await setup_prospect_supporter_kanal()
            await setup_opgave_oprettelse_kanal()
            await setup_prospect_supporter_stats_kanal()
            
            embed = discord.Embed(
                title="✅ System Nulstillet",
                description="Alle jobs og statistikker er blevet nulstillet!",
                color=0x00FF00
            )
            embed.set_thumbnail(url=LOGO_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"⛔ Fejl ved nulstilling: {e}", ephemeral=True)



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
            "point_reward": 0,  # Points tildeles når opgaven lukkes
            "oprettet_af": interaction.user.id,
            "oprettet_navn": interaction.user.display_name
        }
        
        if add_member_job(ny_opgave):
            await interaction.response.send_message("✅ Din opgave er blevet oprettet og sendt til prospect_supporterne!", ephemeral=True)
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
        else:
            await interaction.response.send_message("⛔ Fejl ved oprettelse af opgave!", ephemeral=True)

class CompleteJobModal(Modal):
    def __init__(self, job_id, channel):
        super().__init__(title="✅ Afslut Opgave")
        self.job_id = job_id
        self.channel = channel
        
        self.point_reward = TextInput(
            label="Point Reward (valgfri)",
            placeholder="Indtast antal point (lad stå tom eller 0 for ingen point)",
            required=False,
            max_length=10
        )
        
        self.add_item(self.point_reward)

    async def on_submit(self, interaction: discord.Interaction):
        # Parse point_reward - tom eller ugyldig = 0
        point_reward = 0
        if self.point_reward.value.strip():
            try:
                point_reward = int(self.point_reward.value)
            except ValueError:
                await interaction.response.send_message("⛔ Ugyldig point værdi! Indtast et tal eller lad stå tom.", ephemeral=True)
                return
        
        if point_reward < 0:
            await interaction.response.send_message("⛔ Point kan ikke være negative!", ephemeral=True)
            return
        
        # Marker job som færdigt med points
        if complete_member_job_with_points(self.job_id, point_reward):
            if point_reward > 0:
                await interaction.response.send_message(f"🎉 Jobbet er markeret som færdigt! **{point_reward} point** tildelt. Godt arbejde!", ephemeral=False)
            else:
                await interaction.response.send_message("🎉 Jobbet er markeret som færdigt! Godt arbejde!", ephemeral=False)
            
            # Opdater prospect_supporter kanal og stats
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
            
            stats_kanal = bot.get_channel(STATUS_KANAL_ID)
            if stats_kanal:
                await update_prospect_supporter_stats_embed(stats_kanal)
            
            # Slet den private kanal efter 10 sekunder
            await asyncio.sleep(10)
            try:
                await self.channel.delete()
            except:
                pass
        else:
            await interaction.response.send_message("⛔ Fejl ved færdiggørelse af job!", ephemeral=True)

async def send_prospect_supporter_embed(kanal):
    """Send prospect_supporter embed med alle jobs"""
    embed = discord.Embed(
        title="🎯 Red Devils Prospect/Supporter System",
        description="**Oversigt over alle tilgængelige jobs og opgaver**",
        color=0xFFD700  # Guld farve
    )
    embed.set_thumbnail(url=LOGO_URL)
    
    # Permanente opgaver
    permanent_jobs = get_permanent_jobs()
    
    embed.add_field(
        name="🔄 Permanente Opgaver",
        value="Se nummererede permanente opgaver nedenfor",
        inline=False
    )
    
    # Medlems opgaver
    member_jobs = get_member_jobs()
    embed.add_field(
        name="📋 Vigtige Opgaver",
        value="Se medlems opgaver nedenfor" if member_jobs else "```\nIngen opgaver lige nu\n```",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Information",
        value="Tryk på nummerknapperne for at tage opgaver. Permanente opgaver opretter admin-prospect_supporter kanal.",
        inline=False
    )
    
    embed.set_footer(text="Red Devils Prospect/Supporter System v1.0")
    embed.timestamp = datetime.now()
    
    # Send main embed (denne gemmes og opdateres ikke)
    main_msg = await kanal.send(embed=embed)
    
    # Send permanent jobs med knapper
    await send_permanent_jobs_section(kanal, permanent_jobs)
    
    # Send member jobs (opdeles hvis nødvendigt)
    if member_jobs:
        await send_member_jobs_sections(kanal, member_jobs)
    
    return main_msg

async def send_permanent_jobs_section(kanal, permanent_jobs):
    """Send permanent jobs med nummererede knapper"""
    if not permanent_jobs:
        return
    
    # Opret permanent jobs tekst med numre
    perm_text = ""
    for i, job in enumerate(permanent_jobs, 1):
        perm_text += f"**#{i}** {job}\n"
    
    perm_embed = discord.Embed(
        title="🔄 Permanente Opgaver",
        description=perm_text,
        color=0x5865F2
    )
    
    await kanal.send(embed=perm_embed)
    
    # Opret knapper for permanente jobs
    perm_view = await create_permanent_job_buttons_view(permanent_jobs)
    if perm_view.children:
        await kanal.send("**Permanente opgaver:**", view=perm_view)

async def send_member_jobs_sections(kanal, member_jobs):
    """Send member jobs opdelt i sektioner af max 8"""
    JOBS_PER_SECTION = 8
    
    # Opdel jobs i grupper af 8
    for i in range(0, len(member_jobs), JOBS_PER_SECTION):
        section_jobs = member_jobs[i:i + JOBS_PER_SECTION]
        section_number = (i // JOBS_PER_SECTION) + 1
        
        # Opret embed for denne sektion
        member_jobs_text = ""
        for job in section_jobs:
            status_emoji = "🟢" if job["status"] == "ledig" else "🔴"
            job_number = job.get("job_number", "?")
            member_jobs_text += f"**#{job_number}** {status_emoji} **{job['titel']}**\n"
            member_jobs_text += f"       📝 {job['beskrivelse'][:50]}{'...' if len(job['beskrivelse']) > 50 else ''}\n"
            member_jobs_text += f"       💰 {job['belonning']}\n"
            member_jobs_text += f"       👤 Af: {job['oprettet_navn']}\n"
            if job["status"] == "optaget":
                member_jobs_text += f"       🎯 Prospect/Supporter: {job['prospect_supporter_navn']}\n"
            member_jobs_text += "\n"
        
        # Member jobs embed for denne sektion
        title = f"📋 Vigtige Opgaver (Del {section_number})" if len(member_jobs) > JOBS_PER_SECTION else "📋 Vigtige Opgaver"
        member_embed = discord.Embed(
            title=title,
            description=member_jobs_text,
            color=0x57F287
        )
        
        await kanal.send(embed=member_embed)
        
        # Opret knapper for denne sektion
        section_view = await create_member_job_buttons_view(section_jobs)
        if section_view.children:
            section_label = f"Del {section_number}" if len(member_jobs) > JOBS_PER_SECTION else "opgaver"
            await kanal.send(f"**Medlems {section_label}:**", view=section_view)

async def create_permanent_job_buttons_view(permanent_jobs):
    """Opret view med knapper for permanente jobs"""
    view = View(timeout=None)
    
    for i, job in enumerate(permanent_jobs, 1):
        if len(view.children) >= 25:  # Discord limit
            break
        button = Button(
            label=f"#{i}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"permanent_job_{i}"
        )
        view.add_item(button)
    
    return view

async def create_member_job_buttons_view(jobs):
    """Opret view med knapper for member jobs"""
    view = View(timeout=None)
    
    for job in jobs:
        if job["status"] == "ledig" and len(view.children) < 25:
            job_number = job.get("job_number", "?")
            button = Button(
                label=f"#{job_number}",
                style=discord.ButtonStyle.success,
                custom_id=f"take_job_{job['id']}"
            )
            view.add_item(button)
    
    return view

async def update_prospect_supporter_embed(kanal):
    """Opdater prospect_supporter embed - bevar main info besked"""
    try:
        # Hent alle beskeder i kanalen
        messages = []
        async for message in kanal.history(limit=50):
            if message.author == bot.user:
                messages.append(message)
        
        # Bevar første besked (main info), slet resten
        if len(messages) > 1:
            # Slet alle beskeder undtagen den første (nyeste er først i listen)
            for message in messages[:-1]:  # Alle undtagen den sidste (ældste/første)
                try:
                    await message.delete()
                except:
                    pass
        
        # Send opdaterede sektioner
        permanent_jobs = get_permanent_jobs()
        member_jobs = get_member_jobs()
        
        await send_permanent_jobs_section(kanal, permanent_jobs)
        
        if member_jobs:
            await send_member_jobs_sections(kanal, member_jobs)
        
        # Opdater knapper i alle aktive private kanaler
        await update_all_private_channel_buttons()
        
    except Exception as e:
        print(f"Fejl ved opdatering af prospect_supporter embed: {e}")
        # Fallback: purge og send helt nyt
        try:
            await kanal.purge()
            await send_prospect_supporter_embed(kanal)
        except Exception as e2:
            print(f"Fallback fejl: {e2}")

async def update_all_private_channel_buttons():
    """Opdater knapper i alle aktive private kanaler"""
    try:
        active_channels = get_all_active_private_channels()
        
        for channel_id, job_id in active_channels:
            if channel_id:
                await update_private_channel_buttons(channel_id, job_id)
                
    except Exception as e:
        print(f"Fejl ved opdatering af private kanal knapper: {e}")

async def update_private_channel_buttons(channel_id, job_id):
    """Opdater knapper i en specifik privat kanal"""
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            return
        
        # Find "Kontrol Panel" beskeden med knapper
        control_panel_message = None
        async for message in channel.history(limit=20):
            if (message.author == bot.user and 
                message.components and 
                message.content and 
                "Kontrol Panel" in message.content):
                control_panel_message = message
                break
        
        if control_panel_message:
            # Hent opdateret job data
            job = get_member_job_by_id(job_id)
            if not job:
                return
            
            # Opret nye knapper med opdateret data
            new_control_view = JobControlView(job_id)
            
            # Rediger kun knapperne, bevar beskeden
            try:
                await control_panel_message.edit(content="**🔄 Opdateret Kontrol Panel:**", view=new_control_view)
                print(f"✅ Opdaterede knapper i kanal {channel_id}")
            except Exception as edit_error:
                print(f"Fejl ved redigering af kontrol panel: {edit_error}")
                # Hvis redigering fejler, send ny besked
                new_control_view = JobControlView(job_id)
                await channel.send("**🔄 Nyt Kontrol Panel:**", view=new_control_view)
        else:
            # Hvis ingen kontrol panel findes, opret et nyt
            job = get_member_job_by_id(job_id)
            if job:
                new_control_view = JobControlView(job_id)
                await channel.send("**🔄 Kontrol Panel:**", view=new_control_view)
                
    except Exception as e:
        print(f"Fejl ved opdatering af private kanal {channel_id}: {e}")


async def send_opgave_oprettelse_embed(kanal):
    """Send medlem embed med knap til at oprette opgaver"""
    embed = discord.Embed(
        title="📝 Opret Prospect/Supporter Opgave",
        description="**Har du brug for hjælp fra vores prospect_supporterne?**",
        color=0x5865F2  # Discord blå
    )
    embed.set_thumbnail(url=LOGO_URL)
    
    embed.add_field(
        name="🎯 Sådan fungerer det",
        value=(
            "1️⃣ Tryk på knappen nedenfor\n"
            "2️⃣ Udfyld formularen med din opgave\n"
            "3️⃣ En prospect_supporter vil tage dit job\n"
            "4️⃣ I får en privat kanal til at snakke sammen"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value=(
            "• Vær specifik i din beskrivelse\n"
            "• Angiv belønning hvis relevant\n"
            "• Vær klar til at svare når en prospect_supporter tager jobbet"
        ),
        inline=False
    )
    
    embed.set_footer(text="Red Devils Prospect/Supporter System v1.0")
    
    view = MedlemView()
    await kanal.send(embed=embed, view=view)

async def setup_prospect_supporter_stats_kanal():
    """Setup prospect_supporter statistik kanal"""
    kanal = bot.get_channel(STATUS_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Prospect/Supporter stats kanal med ID {STATUS_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Clear channel
        await kanal.purge()
        print(f"🧹 Prospect/Supporter stats kanal {kanal.name} er ryddet.")
    except Exception as e:
        print(f"❌ Fejl under rydning af prospect_supporter stats kanal: {e}")
    
    # Send stats embed
    await send_prospect_supporter_stats_embed(kanal)

async def setup_admin_panel_kanal():
    """Setup admin panel kanal - sletter gamle beskeder og sender nyt kontrolpanel"""
    kanal = bot.get_channel(ADMIN_PANEL_KANAL_ID)
    if kanal is None:
        print(f"⚠️ Admin panel kanal med ID {ADMIN_PANEL_KANAL_ID} ikke fundet.")
        return
    
    try:
        # Slet kun bottens beskeder i kanalen
        async for message in kanal.history(limit=50):
            if message.author == bot.user:
                try:
                    await message.delete()
                except:
                    pass
        print(f"🧹 Admin panel kanal {kanal.name} er ryddet for bot beskeder.")
    except Exception as e:
        print(f"❌ Fejl under rydning af admin panel kanal: {e}")
    
    # Send admin panel embed
    await send_admin_panel_embed(kanal)

async def send_admin_panel_embed(kanal):
    """Send admin kontrolpanel embed"""
    embed = discord.Embed(
        title="🔧 Red Devils Admin Kontrol Panel",
        description="**Kontrolpanel for administratorer**",
        color=0xFF5733
    )
    embed.set_thumbnail(url=LOGO_URL)
    embed.add_field(
        name="🔄 Permanente Opgaver",
        value="Tilføj, rediger eller fjern permanente opgaver",
        inline=False
    )
    embed.add_field(
        name="📋 Vigtig Opgaver",
        value="Slet medlemsopgaver og opdater kanaler",
        inline=False
    )
    embed.add_field(
        name="🔄 System Opdateringer",
        value="Opdater stats, kanaler eller nulstil systemet",
        inline=False
    )
    embed.set_footer(text="Red Devils Admin System v1.0")
    embed.timestamp = datetime.now()
    
    admin_view = AdminControlView()
    await kanal.send(embed=embed, view=admin_view)
    print(f"✅ Admin kontrolpanel sendt til {kanal.name}")

# Disabled: Markbetalinger
# async def setup_markbetalinger_kanal():
#     """Setup markbetalinger kanal"""
#     kanal = bot.get_channel(MARKBETALINGS_KANAL_ID)
#     if kanal is None:
#         print(f"⚠️ Markbetalinger kanal med ID {MARKBETALINGS_KANAL_ID} ikke fundet.")
#         return
#     
#     try:
#         # Clear channel
#         await kanal.purge()
#         print(f"🧹 Markbetalinger kanal {kanal.name} er ryddet.")
#     except Exception as e:
#         print(f"❌ Fejl under rydning af markbetalinger kanal: {e}")
#     
#     # Send markbetalinger embed
#     await send_markbetalinger_embed(kanal)

# Disabled: Markbetalinger
# async def send_markbetalinger_embed(kanal):
#     """Send markbetalinger embed med liste over betalinger"""
#     # Send hoved-embed først med knap
#     main_embed = discord.Embed(
#         title="💳 Markbetalinger System",
#         description="**Oversigt over alle markbetalinger**",
#         color=0x00FF00
#     )
#     main_embed.set_thumbnail(url=LOGO_URL)
#     main_embed.add_field(
#         name="ℹ️ Information",
#         value="Tryk på knappen nedenfor for at tilføje en ny betaling.",
#         inline=False
#     )
#     main_embed.set_footer(text="Red Devils Markbetalinger System v1.0")
#     main_embed.timestamp = datetime.now()
#     
#     view = MarkbetalingView()
#     await kanal.send(embed=main_embed, view=view)
#     
#     # Hent alle betalinger
#     betalinger = get_markbetalinger()
#     
#     if not betalinger:
#         # Send tom liste besked
#         empty_embed = discord.Embed(
#             title="📋 Betalingsliste",
#             description="```\nIngen betalinger registreret endnu\n```",
#             color=0x00FF00
#         )
#         await kanal.send(embed=empty_embed)
#         return
#     
#     # Send betalingsliste opdelt i sektioner hvis nødvendigt
#     await send_markbetalinger_sections(kanal, betalinger)

# Disabled: Markbetalinger
# async def send_markbetalinger_sections(kanal, betalinger):
#     """Send markbetalinger opdelt i sektioner for at undgå Discord limits"""
#     # Discord field value limit er 1024 tegn
#     # Hver betaling linje er ca 60-70 tegn, så vi kan have ca 15-17 per sektion
#     BETALINGER_PER_SECTION = 15
#     nu_tid = datetime.now()
#     
#     # Opdel betalinger i grupper
#     for i in range(0, len(betalinger), BETALINGER_PER_SECTION):
#         section_betalinger = betalinger[i:i + BETALINGER_PER_SECTION]
#         section_number = (i // BETALINGER_PER_SECTION) + 1
#         
#         # Opret liste format
#         betalingsliste_text = "```\n"
#         for betaling in section_betalinger:
#             navn_padded = betaling["navn"][:20].ljust(20)
#             telefon_padded = betaling["telefon"][:15].ljust(15)
#             tidsperiode = betaling["tidsperiode"]
#             
#             # Beregn nedtælling (tid tilbage)
#             if betaling["udlobsdato"]:
#                 udlobs_dato = datetime.strptime(betaling["udlobsdato"], "%Y-%m-%d %H:%M:%S")
#                 tid_tilbage = udlobs_dato - nu_tid
#                 
#                 if tid_tilbage.total_seconds() <= 0:
#                     nedtaelling = "Udløbet"
#                 else:
#                     dage = tid_tilbage.days
#                     timer, rest = divmod(tid_tilbage.seconds, 3600)
#                     minutter, _ = divmod(rest, 60)
#                     
#                     if dage > 0:
#                         nedtaelling = f"{dage}d {timer}t"
#                     elif timer > 0:
#                         nedtaelling = f"{timer}t {minutter}m"
#                     else:
#                         nedtaelling = f"{minutter}m"
#             else:
#                 nedtaelling = "Ukendt"
#             
#             betalingsliste_text += f"{navn_padded} {telefon_padded} {tidsperiode:<10} {nedtaelling}\n"
#         betalingsliste_text += "```"
#         
#         # Opret embed for denne sektion
#         title = f"📋 Betalingsliste (Del {section_number})" if len(betalinger) > BETALINGER_PER_SECTION else "📋 Betalingsliste"
#         section_embed = discord.Embed(
#             title=title,
#             description=betalingsliste_text,
#             color=0x00FF00
#         )
#         
#         await kanal.send(embed=section_embed)

def get_prospect_supporter_stats():
    """Get prospect_supporter statistics from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT prospect_supporter_id, prospect_supporter_navn, total_points 
            FROM prospect_supporter_stats 
            ORDER BY total_points DESC
        """)
        stats = cursor.fetchall()
        conn.close()
        return stats
    except Exception as e:
        print(f"Fejl ved hentning af prospect_supporter stats: {e}")
        return []

def get_current_supporter_stats(guild):
    """Get supporter stats kun for folk med supporter rollen lige nu"""
    try:
        supporter_role = discord.utils.get(guild.roles, id=SUPPORTER_ROLLE_ID)
        if not supporter_role:
            return []
        
        current_supporter_ids = [member.id for member in supporter_role.members]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if current_supporter_ids:
            placeholders = ','.join(['?' for _ in current_supporter_ids])
            cursor.execute(f"""
            SELECT prospect_supporter_id, prospect_supporter_navn, total_points 
            FROM prospect_supporter_stats 
            WHERE prospect_supporter_id IN ({placeholders})
            ORDER BY total_points DESC
            """, current_supporter_ids)
            stats = cursor.fetchall()
        else:
            stats = []
        
        conn.close()
        return stats
    except Exception as e:
        print(f"Fejl ved hentning af supporter stats: {e}")
        return []

def get_current_prospect_stats(guild):
    """Get prospect stats kun for folk med prospect rollen lige nu"""
    try:
        prospect_role = discord.utils.get(guild.roles, id=PROSPECT_ROLLE_ID)
        if not prospect_role:
            return []
        
        current_prospect_ids = [member.id for member in prospect_role.members]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if current_prospect_ids:
            placeholders = ','.join(['?' for _ in current_prospect_ids])
            cursor.execute(f"""
            SELECT prospect_supporter_id, prospect_supporter_navn, total_points 
            FROM prospect_supporter_stats 
            WHERE prospect_supporter_id IN ({placeholders})
            ORDER BY total_points DESC
            """, current_prospect_ids)
            stats = cursor.fetchall()
        else:
            stats = []
        
        conn.close()
        return stats
    except Exception as e:
        print(f"Fejl ved hentning af prospect stats: {e}")
        return []

def get_current_prospect_supporter_stats(guild):
    """Get prospect_supporter stats kun for folk med prospect_supporter rollen lige nu"""
    try:
        # Kombiner supporter og prospect stats
        supporter_stats = get_current_supporter_stats(guild)
        prospect_stats = get_current_prospect_stats(guild)
        return supporter_stats + prospect_stats
    except Exception as e:
        print(f"Fejl ved hentning af aktuelle prospect_supporter stats: {e}")
        return []

def get_recent_completed_jobs(limit=5):
    """Get recent completed jobs from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT titel, prospect_supporter_navn, completed_tid, job_number
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

def get_recent_completed_jobs_current_prospect_supporters(guild, limit=5):
    """Get recent completed jobs kun fra folk der stadig har prospect_supporter rollen"""
    try:
        prospect_supporter_role = discord.utils.get(guild.roles, id=PROSPECT_SUPPORTER_ROLLE_IDS[0])
        if not prospect_supporter_role:
            return []
        
        # Hent alle prospect_supporter IDs der har rollen lige nu
        current_prospect_supporter_ids = [member.id for member in prospect_supporter_role.members]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if current_prospect_supporter_ids:
            placeholders = ','.join(['?' for _ in current_prospect_supporter_ids])
            cursor.execute(f"""
                SELECT titel, prospect_supporter_navn, completed_tid, job_number
                FROM completed_jobs 
                WHERE prospect_supporter_id IN ({placeholders})
                ORDER BY completed_tid DESC 
                LIMIT ?
            """, current_prospect_supporter_ids + [limit])
            jobs = cursor.fetchall()
        else:
            jobs = []
        
        conn.close()
        return jobs
    except Exception as e:
        print(f"Fejl ved hentning af seneste jobs fra aktuelle prospect_supporterne: {e}")
        return []

async def ensure_all_prospect_supporters_in_stats(guild):
    """Sørg for at alle med prospect_supporter/supporter/prospect rollen er i statistik tabellen og fjern gamle"""
    try:
        supporter_role = discord.utils.get(guild.roles, id=SUPPORTER_ROLLE_ID)
        prospect_role = discord.utils.get(guild.roles, id=PROSPECT_ROLLE_ID)
        
        all_members = []
        if supporter_role:
            all_members.extend(supporter_role.members)
        if prospect_role:
            all_members.extend(prospect_role.members)
        
        # Fjern duplikater
        all_members = list({member.id: member for member in all_members}.values())
        
        current_prospect_supporter_ids = [member.id for member in all_members]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Indsæt alle aktuelle members i tabellen hvis de ikke allerede er der
        for member in all_members:
            cursor.execute("""
                INSERT OR IGNORE INTO prospect_supporter_stats (prospect_supporter_id, prospect_supporter_navn, total_points)
                VALUES (?, ?, 0)
            """, (member.id, member.display_name))
        
        # Opdater navne for eksisterende members
        for member in all_members:
            cursor.execute("""
                UPDATE prospect_supporter_stats 
                SET prospect_supporter_navn = ?, last_updated = CURRENT_TIMESTAMP
                WHERE prospect_supporter_id = ?
            """, (member.display_name, member.id))
        
        # VIGTIGT: Marker folk uden rolle som inaktive
        # Vi sletter ikke deres data, men de vises ikke i listen
        if current_prospect_supporter_ids:
            placeholders = ','.join(['?' for _ in current_prospect_supporter_ids])
            cursor.execute(f"""
                UPDATE prospect_supporter_stats 
                SET last_updated = CURRENT_TIMESTAMP
                WHERE prospect_supporter_id NOT IN ({placeholders})
            """, current_prospect_supporter_ids)
        
        conn.commit()
        conn.close()
        print(f"✅ Real-time opdaterede stats for {len(all_members)} aktive members ({len(supporter_role.members) if supporter_role else 0} supporters, {len(prospect_role.members) if prospect_role else 0} prospects)")
        
    except Exception as e:
        print(f"Fejl ved real-time opdatering af prospect_supporter stats: {e}")

async def send_prospect_supporter_stats_embed(kanal):
    """Send prospect_supporter statistik embed med separate lister for supporters og prospects"""
    # Sørg for alle prospect_supporterne er i databasen
    await ensure_all_prospect_supporters_in_stats(kanal.guild)
    
    embed = discord.Embed(
        title="📊 Prospect/Supporter Statistikker",
        description="**Oversigt over alle supporters og prospects og deres points**",
        color=0x00FF00
    )
    embed.set_thumbnail(url=LOGO_URL)
    
    # Get supporter stats
    supporter_stats = get_current_supporter_stats(kanal.guild)
    if supporter_stats:
        supporter_text = "```\n"
        for i, (supporter_id, supporter_navn, total_points) in enumerate(supporter_stats, 1):
            navn_padded = supporter_navn[:20].ljust(20)
            supporter_text += f"{i:2d}. {navn_padded} {total_points:3d} points\n"
        supporter_text += "```"
        
        embed.add_field(
            name="👥 Supporter Rankings",
            value=supporter_text,
            inline=False
        )
    else:
        embed.add_field(
            name="👥 Supporter Rankings",
            value="```\nIngen supporters fundet\n```",
            inline=False
        )
    
    # Get prospect stats
    prospect_stats = get_current_prospect_stats(kanal.guild)
    if prospect_stats:
        prospect_text = "```\n"
        for i, (prospect_id, prospect_navn, total_points) in enumerate(prospect_stats, 1):
            navn_padded = prospect_navn[:20].ljust(20)
            prospect_text += f"{i:2d}. {navn_padded} {total_points:3d} points\n"
        prospect_text += "```"
        
        embed.add_field(
            name="🎯 Prospect Rankings",
            value=prospect_text,
            inline=False
        )
    else:
        embed.add_field(
            name="🎯 Prospect Rankings",
            value="```\nIngen prospects fundet\n```",
            inline=False
        )
    
    # Recent completed jobs med mørkeblå felt stil (kun fra aktuelle prospect_supporterne)
    recent_jobs = get_recent_completed_jobs_current_prospect_supporters(kanal.guild, 5)
    if recent_jobs:
        recent_text = "```\n"
        for titel, prospect_supporter_navn, completed_tid, job_number in recent_jobs:
            date_str = completed_tid[:10] if completed_tid else "?"
            titel_short = titel[:25] + "..." if len(titel) > 25 else titel
            recent_text += f"#{job_number:2d} {titel_short.ljust(28)} {prospect_supporter_navn[:15]}\n"
            recent_text += f"    {date_str}\n\n"
        recent_text += "```"
        
        embed.add_field(
            name="🕒 Seneste Færdiggjorte Jobs", 
            value=recent_text,
            inline=False
        )
    else:
        embed.add_field(
            name="🕒 Seneste Færdiggjorte Jobs",
            value="```\nIngen færdiggjorte jobs endnu\n```",
            inline=False
        )
    
    embed.set_footer(text="Red Devils Prospect/Supporter Stats v1.0")
    embed.timestamp = datetime.now()
    
    # Send kun én embed (som på billedet)
    await kanal.send(embed=embed)

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
        
        # Tjek om brugeren er medlem eller prospect_supporter på jobbet (DEV rolle bypasser)
        if not tjek_dev_rolle(interaction.user) and interaction.user.id not in [job["oprettet_af"], job.get("prospect_supporter_id")]:
            await interaction.response.send_message("⛔ Du kan kun cancellere jobs du er involveret i!", ephemeral=True)
            return
        
        # Cancel jobbet
        if update_member_job_status(self.job_id, "ledig"):
            await interaction.response.send_message("✅ Jobbet er blevet cancelled og er nu ledigt igen!", ephemeral=False)
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
            
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
        
        # Tjek om brugeren er medlemmet der oprettede jobbet (DEV rolle bypasser)
        if not tjek_dev_rolle(interaction.user) and interaction.user.id != job.get("oprettet_af"):
            await interaction.response.send_message("⛔ Kun medlemmet der oprettede jobbet kan markere det som færdigt!", ephemeral=True)
            return
        
        # Vis modal til at indtaste point reward
        await interaction.response.send_modal(CompleteJobModal(self.job_id, interaction.channel))

    @discord.ui.button(label="🔨 FORCE LUK", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def force_close(self, interaction: discord.Interaction, button: Button):
        # Tjek om brugeren er super admin eller dev (DEV rolle bypasser)
        if not tjek_dev_rolle(interaction.user) and interaction.user.id != ABSOLUT_ADMIN_ID:
            await interaction.response.send_message("⛔ Kun super admin kan force-lukke tickets!", ephemeral=True)
            return
        
        await interaction.response.send_message("⚠️ **FORCE LUK** - Kanalen lukkes om 5 sekunder af super admin...", ephemeral=False)
        
        # Marker job som cancelled hvis det stadig eksisterer
        job = get_member_job_by_id(self.job_id)
        if job and job["status"] != "faerdig":
            update_member_job_status(self.job_id, "ledig")
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
        
        # Slet kanalen efter 5 sekunder
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

async def update_prospect_supporter_stats_embed(kanal):
    """Opdater prospect_supporter stats embed"""
    try:
        await kanal.purge()
        await send_prospect_supporter_stats_embed(kanal)
    except Exception as e:
        print(f"Fejl ved opdatering af prospect_supporter stats embed: {e}")

@bot.event
async def on_interaction(interaction):
    """Handle button interactions"""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id.startswith("take_job_"):
            await handle_take_job(interaction, custom_id)
        elif custom_id.startswith("permanent_job_"):
            await handle_permanent_job(interaction, custom_id)

async def handle_permanent_job(interaction, custom_id):
    """Handle når en prospect_supporter tager en permanent opgave"""
    job_number = int(custom_id.replace("permanent_job_", ""))
    
    # Hent permanent jobs
    permanent_jobs = get_permanent_jobs()
    
    if job_number < 1 or job_number > len(permanent_jobs):
        await interaction.response.send_message("⛔ Ugyldig opgave nummer!", ephemeral=True)
        return
    
    job_title = permanent_jobs[job_number - 1]
    prospect_supporter = interaction.user
    
    # Tjek om brugeren har admin rolle for at finde admin
    # DEV rolle bypasser alt - tjek først
    if tjek_dev_rolle(prospect_supporter):
        # Dev rolle kan altid tage permanente opgaver
        pass
    elif tjek_admin_rolle(prospect_supporter):
        await interaction.response.send_message("⛔ Admins kan ikke tage permanente opgaver!", ephemeral=True)
        return
    
    admin_user = None
    
    # Find en admin til at koordinere med
    guild = interaction.guild
    admin_members = []
    
    # Saml alle medlemmer med admin roller
    for admin_role_id in ADMIN_ROLLE_IDS:
        admin_role = discord.utils.get(guild.roles, id=admin_role_id)
        if admin_role and admin_role.members:
            admin_members.extend(admin_role.members)
    
    # Fjern duplikater
    admin_members = list(set(admin_members))
    
    if not admin_members:
        await interaction.response.send_message("⛔ Ingen admins tilgængelige!", ephemeral=True)
        return
    
    # Tag første tilgængelige admin
    admin_user = admin_members[0]
    
    # Opret privat kanal
    try:
        kategori = discord.utils.get(guild.categories, id=PRIVAT_KATEGORI_ID)
        
        if not kategori:
            await interaction.response.send_message("⛔ Kunne ikke finde kategorien til private kanaler!", ephemeral=True)
            return
        
        # Opret kanal navn
        kanal_navn = f"perm-{job_number}-{prospect_supporter.display_name[:10]}"
        
        # Opret kanalen
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            admin_user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            prospect_supporter: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        privat_kanal = await kategori.create_text_channel(
            name=kanal_navn,
            overwrites=overwrites
        )
        
        # Send besked i den private kanal
        perm_embed = discord.Embed(
            title="🔄 Permanent Opgave Match!",
            description=f"**{prospect_supporter.display_name}** vil arbejde på permanent opgave med **{admin_user.display_name}**",
            color=0x5865F2
        )
        
        perm_embed.add_field(
            name="📋 Opgave",
            value=f"**#{job_number}** {job_title}",
            inline=False
        )
        
        perm_embed.add_field(
            name="👥 Deltagere",
            value=f"**Prospect/Supporter:** {prospect_supporter.mention}\n**Admin:** {admin_user.mention}",
            inline=False
        )
        
        perm_embed.add_field(
            name="ℹ️ Information",
            value="I kan nu koordinere arbejdet på denne permanente opgave. Kanalen slettes ikke automatisk.",
            inline=False
        )
        
        perm_embed.set_footer(text="Permanent Opgave Koordination")
        
        # Opret view med close og point knapper
        perm_view = PermanentJobView(job_number, job_title, prospect_supporter.id)
        
        await privat_kanal.send(f"{admin_user.mention} {prospect_supporter.mention}", embed=perm_embed, view=perm_view)
        
        await interaction.response.send_message(f"✅ Permanent opgave taget! Privat kanal oprettet: {privat_kanal.mention}", ephemeral=True)
        
    except Exception as e:
        print(f"Fejl ved oprettelse af permanent opgave kanal: {e}")
        await interaction.response.send_message("⛔ Fejl ved oprettelse af privat kanal!", ephemeral=True)

class PermanentJobView(View):
    def __init__(self, job_number, job_title, prospect_supporter_id=None):
        super().__init__(timeout=None)
        self.job_number = job_number
        self.job_title = job_title
        self.prospect_supporter_id = prospect_supporter_id

    @discord.ui.button(label="✅ Afslut & Giv Point", style=discord.ButtonStyle.success)
    async def complete_with_points(self, interaction: discord.Interaction, button: Button):
        # Tjek om brugeren er admin (DEV rolle bypasser)
        if not tjek_dev_rolle(interaction.user) and not tjek_admin_rolle(interaction.user):
            await interaction.response.send_message("⛔ Kun admins kan afslutte permanente opgaver med point!", ephemeral=True)
            return
        
        # Vis modal til at indtaste point reward
        await interaction.response.send_modal(CompletePermanentJobModal(self.prospect_supporter_id, interaction.channel))

    @discord.ui.button(label="🔒 Luk Kanal", style=discord.ButtonStyle.danger)
    async def close_channel(self, interaction: discord.Interaction, button: Button):
        # Tjek om brugeren er admin eller prospect_supporter i kanalen (DEV rolle bypasser)
        if not tjek_dev_rolle(interaction.user) and not (tjek_admin_rolle(interaction.user) or 
                interaction.channel.permissions_for(interaction.user).send_messages):
            await interaction.response.send_message("⛔ Du har ikke tilladelse til at lukke denne kanal!", ephemeral=True)
            return
        
        await interaction.response.send_message("🔒 Kanalen lukkes om 10 sekunder...", ephemeral=False)
        
        # Slet kanalen efter 10 sekunder
        await asyncio.sleep(10)
        try:
            await interaction.channel.delete()
        except:
            pass

    @discord.ui.button(label="🔨 FORCE LUK", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def force_close(self, interaction: discord.Interaction, button: Button):
        # Tjek om brugeren er super admin eller dev (DEV rolle bypasser)
        if not tjek_dev_rolle(interaction.user) and interaction.user.id != ABSOLUT_ADMIN_ID:
            await interaction.response.send_message("⛔ Kun super admin kan force-lukke tickets!", ephemeral=True)
            return
        
        await interaction.response.send_message("⚠️ **FORCE LUK** - Kanalen lukkes om 5 sekunder af super admin...", ephemeral=False)
        
        # Slet kanalen efter 5 sekunder
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

class CompletePermanentJobModal(Modal):
    def __init__(self, prospect_supporter_id, channel):
        super().__init__(title="✅ Afslut Permanent Opgave")
        self.prospect_supporter_id = prospect_supporter_id
        self.channel = channel
        
        self.point_reward = TextInput(
            label="Point Reward (valgfri)",
            placeholder="Indtast antal point (lad stå tom eller 0 for ingen point)",
            required=False,
            max_length=10
        )
        
        self.add_item(self.point_reward)

    async def on_submit(self, interaction: discord.Interaction):
        # Parse point_reward - tom eller ugyldig = 0
        point_reward = 0
        if self.point_reward.value.strip():
            try:
                point_reward = int(self.point_reward.value)
            except ValueError:
                await interaction.response.send_message("⛔ Ugyldig point værdi! Indtast et tal eller lad stå tom.", ephemeral=True)
                return
        
        if point_reward < 0:
            await interaction.response.send_message("⛔ Point kan ikke være negative!", ephemeral=True)
            return
        
        # Giv point til prospect_supporter hvis der er nogen
        if point_reward > 0 and self.prospect_supporter_id:
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                # Hent prospect_supporter navn fra guild
                guild = interaction.guild
                member = guild.get_member(self.prospect_supporter_id)
                prospect_supporter_navn = member.display_name if member else "Ukendt"
                
                # Update prospect_supporter stats with points
                cursor.execute("""
                    INSERT OR REPLACE INTO prospect_supporter_stats (prospect_supporter_id, prospect_supporter_navn, total_points)
                    VALUES (?, ?, COALESCE((SELECT total_points FROM prospect_supporter_stats WHERE prospect_supporter_id = ?), 0) + ?)
                """, (self.prospect_supporter_id, prospect_supporter_navn, self.prospect_supporter_id, point_reward))
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Fejl ved tildeling af point: {e}")
        
        if point_reward > 0:
            await interaction.response.send_message(f"🎉 Permanent opgave afsluttet! **{point_reward} point** tildelt. Kanalen lukkes om 10 sekunder...", ephemeral=False)
        else:
            await interaction.response.send_message("🎉 Permanent opgave afsluttet! Kanalen lukkes om 10 sekunder...", ephemeral=False)
        
        # Opdater stats kanal
        stats_kanal = bot.get_channel(STATUS_KANAL_ID)
        if stats_kanal:
            await update_prospect_supporter_stats_embed(stats_kanal)
        
        # Slet den private kanal efter 10 sekunder
        await asyncio.sleep(10)
        try:
            await self.channel.delete()
        except:
            pass

async def handle_take_job(interaction, custom_id):
    """Handle når en prospect_supporter tager et job"""
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
        
        # Hent medlem og prospect_supporter
        medlem = await bot.fetch_user(job["oprettet_af"])
        prospect_supporter = interaction.user
        
        # Opret kanal navn
        kanal_navn = f"job-{job['id']}-{medlem.display_name[:10]}"
        
        # Opret kanalen
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            medlem: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            prospect_supporter: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        privat_kanal = await kategori.create_text_channel(
            name=kanal_navn,
            overwrites=overwrites
        )
        
        # Send besked i den private kanal
        job_embed = discord.Embed(
            title="🤝 Job Match!",
            description=f"**{prospect_supporter.display_name}** har taget jobbet fra **{medlem.display_name}**",
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
        
        # Send initial besked uden knapper
        await privat_kanal.send(f"{medlem.mention} {prospect_supporter.mention}", embed=job_embed)
        
        # Send separat besked med knapper (denne kan opdateres senere)
        control_view = JobControlView(job_id)
        await privat_kanal.send("**Kontrol Panel:**", view=control_view)
        
        # Gem kanal ID til jobbet
        update_private_channel_id(job_id, privat_kanal.id)
        
        await interaction.response.send_message(f"✅ Du har taget jobbet! Privat kanal oprettet: {privat_kanal.mention}", ephemeral=True)
        
        # Opdater prospect_supporter kanal
        prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
        if prospect_supporter_kanal:
            await update_prospect_supporter_embed(prospect_supporter_kanal)
            
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
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
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
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
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
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
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

def tjek_dev_rolle(user):
    """Tjek om brugeren har dev rollen - bypasser alle checks"""
    return user.id == ABSOLUT_ADMIN_ID or any(role.id == DEV_ROLLE_ID for role in user.roles)

def tjek_admin_rolle(user):
    """Tjek om brugeren har admin rollen, dev rollen eller er absolut admin"""
    if tjek_dev_rolle(user):
        return True
    return user.id == ABSOLUT_ADMIN_ID or any(role.id in ADMIN_ROLLE_IDS for role in user.roles)

def tjek_medlem_rolle(user):
    """Tjek om brugeren har medlem rollen eller dev rollen"""
    if tjek_dev_rolle(user):
        return True
    return user.get_role(FULDT_MEDLEM_ROLLE_ID) is not None

@bot.command(name="prospect_supporterbot", aliases=["prospectbot"])
async def prospect_supporterbot_admin(ctx):
    """Admin kommandoer til prospect_supporter bot"""
    
    # Tjek admin rolle
    if not tjek_admin_rolle(ctx.author):
        await ctx.send("⛔ Du har ikke tilladelse til at bruge admin kommandoer!")
        return
    
    # Slet kommandoen
    try:
        await ctx.message.delete()
    except:
        pass
    
    embed = discord.Embed(
        title="🔧 Red Devils Admin Kontrol Panel",
        description="**Kun synligt for administratorer**",
        color=0xFF5733
    )
    embed.set_thumbnail(url=LOGO_URL)
    embed.add_field(
        name="🔄 Permanente Opgaver",
        value="Tilføj, rediger eller fjern permanente opgaver",
        inline=False
    )
    embed.add_field(
        name="📋 Vigtig Opgaver",
        value="Slet medlemsopgaver og opdater kanaler",
        inline=False
    )
    embed.add_field(
        name="🔄 System Opdateringer",
        value="Opdater stats, kanaler eller nulstil systemet",
        inline=False
    )
    embed.set_footer(text="Kun du kan se denne.")
    
    admin_view = AdminControlView()
    
    # Send kontrolpanelet i den faste admin-panel kanal
    kanal = bot.get_channel(ADMIN_PANEL_KANAL_ID)
    if kanal:
        await kanal.send(embed=embed, view=admin_view)
    else:
        # Fallback: send i den kanal hvor kommandoen blev kørt
        await ctx.send(embed=embed, view=admin_view)

@bot.command(name="prospect_supporterbot_old")
async def prospect_supporterbot_admin_old(ctx, action=None, subaction=None, *args):
    """Gamle admin kommandoer til prospect_supporter bot (backup)"""
    
    # Tjek admin rolle
    if not tjek_admin_rolle(ctx.author):
        await ctx.send("⛔ Du har ikke tilladelse til at bruge admin kommandoer!")
        return
    
    if action.lower() not in ["permopg", "mopg"]:
        await ctx.send("⛔ Ukendt kommando! Brug `!prospect_supporterbot permopg [add/edit/remove]` eller `!prospect_supporterbot mopg del [nummer]`")
        return
    
    # Handle mopg (medlems opgaver) kommandoer
    if action.lower() == "mopg":
        if subaction is None or subaction.lower() != "del":
            await ctx.send("⛔ Brug: `!prospect_supporterbot mopg del [nummer]`")
            return
        
        # Tjek om der er angivet et nummer
        if len(args) == 0:
            await ctx.send("⛔ Du skal angive opgave nummeret! Brug: `!prospect_supporterbot mopg del [nummer]`")
            return
        
        try:
            job_number = int(args[0])
        except ValueError:
            await ctx.send("⛔ Ugyldigt nummer! Brug: `!prospect_supporterbot mopg del [nummer]`")
            return
        
        # Find jobbet
        job = get_member_job_by_number(job_number)
        if not job:
            await ctx.send(f"⛔ Ingen opgave fundet med nummer **{job_number}**!")
            return
        
        # Slet jobbet
        success, privat_kanal_id = delete_member_job_by_id(job["id"])
        
        if success:
            # Luk privat kanal hvis den eksisterer (uden at sende besked)
            if privat_kanal_id:
                privat_kanal = bot.get_channel(privat_kanal_id)
                if privat_kanal:
                    try:
                        await asyncio.sleep(2)  # Kort pause før kanalen lukkes
                        await privat_kanal.delete()
                    except:
                        pass
            
            # Opdater prospect_supporter kanal
            prospect_supporter_kanal = bot.get_channel(OPGAVE_KANAL_ID)
            if prospect_supporter_kanal:
                await update_prospect_supporter_embed(prospect_supporter_kanal)
            
            embed = discord.Embed(
                title="✅ Opgave Slettet",
                description=f"**Opgave #{job_number}** er blevet slettet",
                color=0x00FF00
            )
            embed.add_field(name="Titel", value=job["titel"], inline=False)
            embed.add_field(name="Oprettet af", value=job["oprettet_navn"], inline=True)
            embed.add_field(name="Status", value=job["status"], inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("⛔ Fejl ved sletning af opgave!")
        
        return
    
    # Handle permopg (permanente opgaver) kommandoer
    if subaction is None:
        embed = discord.Embed(
            title="🔧 Permanent Opgave Admin",
            description="**Brug:** `!prospect_supporterbot permopg [add/edit/remove]`",
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
async def refresh_stats(ctx):
    """Genopfrisk prospect_supporter statistikker manuelt (admin kun)"""
    if not tjek_admin_rolle(ctx.author):
        await ctx.send("⛔ Du har ikke tilladelse til at opdatere stats!")
        return
    
    try:
        stats_kanal = bot.get_channel(STATUS_KANAL_ID)
        if stats_kanal:
            await update_prospect_supporter_stats_embed(stats_kanal)
            await ctx.send("✅ Prospect/Supporter statistikker er blevet opdateret!")
        else:
            await ctx.send("⛔ Stats kanal ikke fundet!")
    except Exception as e:
        await ctx.send(f"⛔ Fejl ved opdatering: {e}")
        print(f"Fejl ved manual stats refresh: {e}")

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
        cursor.execute("DELETE FROM prospect_supporter_stats")
        cursor.execute("UPDATE settings SET value = '1' WHERE key = 'job_counter'")
        
        conn.commit()
        conn.close()
        
        # Opdater kanaler
        await setup_prospect_supporter_kanal()
        await setup_opgave_oprettelse_kanal()
        await setup_prospect_supporter_stats_kanal()
        
        await ctx.send("✅ Alle jobs og statistikker er blevet nulstillet!")
        
    except Exception as e:
        await ctx.send(f"⛔ Fejl ved nulstilling: {e}")
        print(f"Fejl ved admin reset: {e}")

@tasks.loop(minutes=5)  # Tjek hver 5. minut som backup
async def periodic_stats_check():
    """Periodisk tjek af prospect_supporter stats og markbetalinger som backup til events"""
    try:
        stats_kanal = bot.get_channel(STATUS_KANAL_ID)
        if stats_kanal:
            # Stille opdatering uden at spamme logs
            await update_prospect_supporter_stats_embed(stats_kanal)
        
        # Disabled: Markbetalinger
        # markbetalinger_kanal = bot.get_channel(MARKBETALINGS_KANAL_ID)
        # if markbetalinger_kanal:
        #     await update_markbetalinger_embed(markbetalinger_kanal)
        
        print("🔄 Periodisk stats og markbetalinger check udført")
    except Exception as e:
        print(f"Fejl ved periodisk check: {e}")

@periodic_stats_check.before_loop
async def before_periodic_check():
    await bot.wait_until_ready()

bot.run(TOKEN)

