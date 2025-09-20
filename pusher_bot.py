import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
from datetime import datetime
import json
import asyncio

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

# Data storage
JOBS_FIL = "jobs_data.json"
jobs_data = {
    "permanent_jobs": [
        "🚗 Køre rundt og sælge stoffer",
        "💰 Hjælpe med money wash",
        "🏠 Hjælpe med hus raids",
        "⚔️ Hjælpe med gang wars",
        "📦 Hjælpe med leveringer",
        "🔫 Hjælpe med våben handel",
        "🎯 Hjælpe med contracts"
    ],
    "member_jobs": [],
    "active_jobs": {},
    "job_counter": 1
}

def load_jobs_data():
    """Load jobs data from file"""
    global jobs_data
    try:
        if os.path.exists(JOBS_FIL):
            with open(JOBS_FIL, "r", encoding="utf-8") as f:
                jobs_data = json.load(f)
    except Exception as e:
        print(f"Fejl ved indlæsning af jobs data: {e}")

def save_jobs_data():
    """Save jobs data to file"""
    try:
        with open(JOBS_FIL, "w", encoding="utf-8") as f:
            json.dump(jobs_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Fejl ved gemning af jobs data: {e}")

@bot.event
async def on_ready():
    print(f"Pusher Bot er online som {bot.user}")
    
    # Load data
    load_jobs_data()
    
    # Setup kanaler
    await setup_pusher_kanal()
    await setup_medlem_kanal()

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
        # Opret ny opgave
        job_id = f"job_{jobs_data['job_counter']}"
        jobs_data['job_counter'] += 1
        
        ny_opgave = {
            "id": job_id,
            "titel": self.opgave_titel.value,
            "beskrivelse": self.opgave_beskrivelse.value,
            "belonning": self.belonning.value if self.belonning.value else "Ikke angivet",
            "oprettet_af": interaction.user.id,
            "oprettet_navn": interaction.user.display_name,
            "status": "ledig",
            "pusher_id": None,
            "pusher_navn": None,
            "oprettet_tid": datetime.now().isoformat()
        }
        
        jobs_data['member_jobs'].append(ny_opgave)
        save_jobs_data()
        
        await interaction.response.send_message("✅ Din opgave er blevet oprettet og sendt til pusherne!", ephemeral=True)
        
        # Opdater pusher kanal
        pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
        if pusher_kanal:
            await update_pusher_embed(pusher_kanal)

async def send_pusher_embed(kanal):
    """Send pusher embed med alle jobs"""
    embed = discord.Embed(
        title="🎯 Vagos Pusher System",
        description="**Oversigt over alle tilgængelige jobs og opgaver**",
        color=0xFFD700  # Guld farve
    )
    
    # Permanente opgaver
    permanent_text = "\n".join([f"• {job}" for job in jobs_data["permanent_jobs"]])
    embed.add_field(
        name="🔄 Permanente Opgaver",
        value=f"```\n{permanent_text}\n```",
        inline=False
    )
    
    # Medlems opgaver
    if jobs_data["member_jobs"]:
        member_jobs_text = ""
        for job in jobs_data["member_jobs"]:
            status_emoji = "🟢" if job["status"] == "ledig" else "🔴"
            member_jobs_text += f"{status_emoji} **{job['titel']}**\n"
            member_jobs_text += f"   └ Af: {job['oprettet_navn']}\n"
            if job["status"] == "optaget":
                member_jobs_text += f"   └ Pusher: {job['pusher_navn']}\n"
            member_jobs_text += "\n"
        
        embed.add_field(
            name="📋 Medlems Opgaver",
            value=member_jobs_text if member_jobs_text else "```\nIngen opgaver lige nu\n```",
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
        value="Tryk på 'Tag Job' knapperne nedenfor for at tage en opgave. Du får adgang til en privat kanal med medlemmet.",
        inline=False
    )
    
    embed.set_footer(text="Vagos Pusher System v1.0")
    embed.timestamp = datetime.now()
    
    # Opret view med knapper for jobs
    view = await create_job_buttons_view()
    
    await kanal.send(embed=embed, view=view)

async def update_pusher_embed(kanal):
    """Opdater pusher embed"""
    # Slet gamle beskeder og send ny
    try:
        await kanal.purge()
        await send_pusher_embed(kanal)
    except Exception as e:
        print(f"Fejl ved opdatering af pusher embed: {e}")

async def create_job_buttons_view():
    """Opret view med knapper for alle ledige jobs"""
    view = View(timeout=None)
    
    # Tilføj knapper for medlems opgaver
    for job in jobs_data["member_jobs"]:
        if job["status"] == "ledig":
            button = Button(
                label=f"Tag Job: {job['titel'][:20]}...",
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
    job = None
    for j in jobs_data["member_jobs"]:
        if j["id"] == job_id:
            job = j
            break
    
    if not job:
        await interaction.response.send_message("⛔ Dette job eksisterer ikke længere!", ephemeral=True)
        return
    
    if job["status"] == "optaget":
        await interaction.response.send_message("⛔ Dette job er allerede taget!", ephemeral=True)
        return
    
    # Marker job som optaget
    job["status"] = "optaget"
    job["pusher_id"] = interaction.user.id
    job["pusher_navn"] = interaction.user.display_name
    job["taget_tid"] = datetime.now().isoformat()
    
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
        
        await privat_kanal.send(f"{medlem.mention} {pusher.mention}", embed=job_embed)
        
        # Gem kanal ID til jobbet
        job["privat_kanal_id"] = privat_kanal.id
        save_jobs_data()
        
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
        
        if ny_opgave in jobs_data["permanent_jobs"]:
            await interaction.response.send_message("⛔ Denne opgave eksisterer allerede!", ephemeral=True)
            return
        
        jobs_data["permanent_jobs"].append(ny_opgave)
        save_jobs_data()
        
        await interaction.response.send_message(f"✅ Permanent opgave tilføjet: {ny_opgave}", ephemeral=True)
        
        # Opdater pusher kanal
        pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
        if pusher_kanal:
            await update_pusher_embed(pusher_kanal)

class EditPermOpgaveModal(Modal):
    def __init__(self, gammel_opgave, index):
        super().__init__(title="✏️ Rediger Permanent Opgave")
        self.index = index
        
        self.opgave_tekst = TextInput(
            label="Opgave Tekst",
            default=gammel_opgave,
            required=True,
            max_length=100
        )
        
        self.add_item(self.opgave_tekst)

    async def on_submit(self, interaction: discord.Interaction):
        ny_tekst = self.opgave_tekst.value
        gammel_tekst = jobs_data["permanent_jobs"][self.index]
        
        jobs_data["permanent_jobs"][self.index] = ny_tekst
        save_jobs_data()
        
        await interaction.response.send_message(f"✅ Opgave opdateret:\n**Fra:** {gammel_tekst}\n**Til:** {ny_tekst}", ephemeral=True)
        
        # Opdater pusher kanal
        pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
        if pusher_kanal:
            await update_pusher_embed(pusher_kanal)

class RemovePermOpgaveSelect(Select):
    def __init__(self):
        options = []
        for i, opgave in enumerate(jobs_data["permanent_jobs"]):
            # Begræns længden af opgave teksten til select menu
            display_text = opgave[:50] + "..." if len(opgave) > 50 else opgave
            options.append(discord.SelectOption(
                label=display_text,
                value=str(i),
                description=f"Fjern denne opgave"
            ))
        
        super().__init__(placeholder="Vælg opgave at fjerne...", options=options, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        fjernet_opgave = jobs_data["permanent_jobs"].pop(index)
        save_jobs_data()
        
        await interaction.response.send_message(f"✅ Permanent opgave fjernet: {fjernet_opgave}", ephemeral=True)
        
        # Opdater pusher kanal
        pusher_kanal = bot.get_channel(PUSHER_KANAL_ID)
        if pusher_kanal:
            await update_pusher_embed(pusher_kanal)

class EditPermOpgaveSelect(Select):
    def __init__(self):
        options = []
        for i, opgave in enumerate(jobs_data["permanent_jobs"]):
            # Begræns længden af opgave teksten til select menu
            display_text = opgave[:50] + "..." if len(opgave) > 50 else opgave
            options.append(discord.SelectOption(
                label=display_text,
                value=str(i),
                description=f"Rediger denne opgave"
            ))
        
        super().__init__(placeholder="Vælg opgave at redigere...", options=options, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        gammel_opgave = jobs_data["permanent_jobs"][index]
        
        # Send modal
        await interaction.response.send_modal(EditPermOpgaveModal(gammel_opgave, index))

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
        if not jobs_data["permanent_jobs"]:
            await ctx.send("⛔ Ingen permanente opgaver at redigere!")
            return
        
        view = View()
        view.add_item(EditPermOpgaveSelect())
        await ctx.send("Vælg opgave at redigere:", view=view)
    
    elif subaction.lower() == "remove":
        if not jobs_data["permanent_jobs"]:
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
        
    jobs_data["member_jobs"] = []
    jobs_data["active_jobs"] = {}
    save_jobs_data()
    
    # Opdater kanaler
    await setup_pusher_kanal()
    await setup_medlem_kanal()
    
    await ctx.send("✅ Alle jobs er blevet nulstillet!")

bot.run(TOKEN)
