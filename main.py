import discord
from discord.ext import commands
from discord import ui
import asyncio
import json
import os
import html
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from threading import Thread


# =========================================================
# KONFIGURACJA
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("Brak DISCORD_TOKEN w zmiennej DISCORD_TOKEN")

TICKET_PANEL_CHANNEL_ID = 1563911023755264133
TICKET_CATEGORY_ID = 1563911023495352410
TRANSCRIPT_CHANNEL_ID = 1563911023495352412
WELCOME_CHANNEL_ID = 1563911023495352416

RECRUITMENT_ROLE_ID = 1563911021863641237
GENERAL_SUPPORT_ROLE_ID = 1563911022270619701
UNIVERSAL_SUPPORT_ROLE_ID = 1563911022270619701

PANEL_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/1508833559551410198/"
    "1548676447579676672/Gemini_Generated_Image_8lu4pd8lu4pd8lu4.jpg"
    "?ex=6aa7ecd6&is=6aa69b56"
    "&hm=76ee4baf615ec0737403f12741f42168b7d6e3db24486e9460eced6071f95bb5"
)

TICKET_IMAGE_URL = PANEL_IMAGE_URL

WELCOME_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/1508833559551410198/"
    "1548676441854705775/Gemini_Generated_Image_o4qcdio4qcdio4qc.jpg"
    "?ex=6aa7ecd4&is=6aa69b54"
    "&hm=562654d9233117f320f4f8bc738d14da08e8e8bffdc4d6252b63c16c077a0c&"
)

TRANSCRIPT_LOADING_IMAGE = (
    "https://cdn.discordapp.com/attachments/1508833559551410198/"
    "1548680146813325363/obraz_2026-09-13_143612130-removebg-preview.png"
    "?ex=6aa7f048&is=6aa69ec8"
    "&hm=bb0cce064bcc6c62ff5e903adfa486cfccfe13e4e051cde1f94596d1a341b760"
)

ARROW = "<a:strzal:1568726971943354459>"
PONNY = "<:ponny:1568727308137922621>"

DATA_DIR = "data"
PANEL_FILE = os.path.join(DATA_DIR, "panel.json")

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

views_registered = False
panel_lock = asyncio.Lock()


# =========================================================
# STATUS
# =========================================================

async def set_bot_status():
    try:
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Game(name="Gildia Ponny Topka")
        )
        print("[STATUS] Nie przeszkadzać | Gildia Ponny Topka")
    except discord.HTTPException as e:
        print(f"[STATUS ERROR] {e}")


# =========================================================
# PANEL JSON
# =========================================================

def save_panel_message_id(message_id: int):
    with open(PANEL_FILE, "w", encoding="utf-8") as f:
        json.dump({"message_id": message_id}, f)


def load_panel_message_id():
    if not os.path.exists(PANEL_FILE):
        return None

    try:
        with open(PANEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("message_id")
    except (OSError, json.JSONDecodeError):
        return None


# =========================================================
# BEZPIECZNE ODPOWIADANIE NA INTERAKCJĘ
# =========================================================

async def safe_ephemeral(
    interaction: discord.Interaction,
    content: str
):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                content,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                content,
                ephemeral=True
            )
    except discord.HTTPException as e:
        print(f"[INTERACTION RESPONSE ERROR] {e}")


# =========================================================
# ROLE / UPRAWNIENIA
# =========================================================

def is_universal_support(member: discord.Member):
    return member.get_role(UNIVERSAL_SUPPORT_ROLE_ID) is not None


def is_general_support(member: discord.Member):
    return member.get_role(GENERAL_SUPPORT_ROLE_ID) is not None


def is_recruitment_support(member: discord.Member):
    return member.get_role(RECRUITMENT_ROLE_ID) is not None


def can_close_ticket(member: discord.Member, ticket_type: str):
    if is_universal_support(member):
        return True

    if is_general_support(member):
        return True

    if (
        ticket_type == "rekrutacja"
        and is_recruitment_support(member)
    ):
        return True

    return False


# =========================================================
# TYP TICKETU
# =========================================================

def get_ticket_type_from_channel(channel):
    if not isinstance(channel, discord.TextChannel):
        return None

    topic = channel.topic or ""

    if "ticket_type=rekrutacja" in topic:
        return "rekrutacja"

    if "ticket_type=klatki" in topic:
        return "klatki"

    if "ticket_type=inne" in topic:
        return "inne"

    return None


# =========================================================
# OWNER ID
# =========================================================

def get_ticket_owner_id(channel):
    if not isinstance(channel, discord.TextChannel):
        return None

    topic = channel.topic or ""

    for part in topic.split("|"):
        if part.startswith("owner_id="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return None

    return None


# =========================================================
# NAZWA TICKETU
# =========================================================

def ticket_name(member: discord.Member, ticket_type: str):
    category_name = {
        "klatki": "klatki",
        "rekrutacja": "rekrutacja",
        "inne": "inne"
    }.get(ticket_type, ticket_type)

    safe_name = (
        member.name
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
    )

    return f"{category_name}-{safe_name}"[:90]


# =========================================================
# SPRAWDZENIE OTWARTEGO TICKETU
# =========================================================

async def user_has_open_ticket(
    guild: discord.Guild,
    user_id: int
):
    category = guild.get_channel(TICKET_CATEGORY_ID)

    if not isinstance(category, discord.CategoryChannel):
        return None

    for channel in category.channels:
        if not isinstance(channel, discord.TextChannel):
            continue

        if get_ticket_owner_id(channel) == user_id:
            return channel

    return None


# =========================================================
# PANEL TICKETÓW
# =========================================================

class TicketSelect(ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Klatki",
                description="Pomoc związana z klatkami",
                value="klatki"
            ),
            discord.SelectOption(
                label="Rekrutacja",
                description="Złóż podanie do Ponny",
                value="rekrutacja"
            ),
            discord.SelectOption(
                label="Inne",
                description="Pozostałe sprawy",
                value="inne"
            )
        ]

        super().__init__(
            placeholder="Wybierz kategorię ticketu...",
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]

        # Ważne: send_modal musi być pierwszą odpowiedzią
        # na tę interakcję. Nie wolno tutaj wcześniej robić
        # defer() ani send_message().
        if ticket_type == "rekrutacja":
            try:
                await interaction.response.send_modal(
                    RecruitmentModal()
                )
            except discord.HTTPException as e:
                print(f"[MODAL ERROR] {e}")

                # Jeśli Discord zwróci 429, nie próbujemy
                # odpowiadać drugi raz przez interaction.response.
            return

        await create_ticket(
            interaction,
            ticket_type
        )


class TicketPanelView(ui.LayoutView):

    def __init__(self):
        super().__init__(timeout=None)

        container = ui.Container()

        gallery = ui.MediaGallery()
        gallery.add_item(media=PANEL_IMAGE_URL)
        container.add_item(gallery)

        container.add_item(
            ui.TextDisplay(
                content=(
                    "## ```🎀 System ticketów```\n"
                    f"{ARROW} ᴡʏʙɪᴇʀᴢ ᴏᴘᴄᴊᴇ ᴢ ᴍᴇɴᴜ ᴘᴏɴɪᴢᴇᴊ.\n"
                    f"{ARROW} ᴜᴢʏᴊ ᴘᴏᴘʀᴀᴡɴᴇᴊ ᴋᴀᴛᴇɢᴏʀɪɪ, "
                    "ᴢᴇʙʏ sᴢʏʙᴄɪᴇᴊ ᴘʀᴢᴇᴊsᴄ ᴘʀᴏᴄᴇs."
                )
            )
        )

        select_row = ui.ActionRow()
        select_row.add_item(TicketSelect())
        container.add_item(select_row)

        self.add_item(container)


# =========================================================
# MODAL REKRUTACJI
# =========================================================

class RecruitmentModal(ui.Modal, title="Rekrutacja"):

    age = ui.TextInput(
        label="Ile masz lat",
        placeholder="Wpisz swój wiek...",
        required=True,
        max_length=3
    )

    name = ui.TextInput(
        label="Imię",
        placeholder="Wpisz swoje imię...",
        required=True,
        max_length=50
    )

    minecraft = ui.TextInput(
        label="Nick Minecraft",
        placeholder="Wpisz swój nick Minecraft...",
        required=True,
        max_length=50
    )

    pvp = ui.TextInput(
        label="Twoje Pvp",
        placeholder="Np. 8/10",
        required=True,
        max_length=20
    )

    why = ui.TextInput(
        label="Dlaczego Ponny",
        placeholder="Dlaczego chcesz dołączyć do Ponny?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await safe_ephemeral(
                interaction,
                "Nie można utworzyć ticketu poza serwerem."
            )
            return

        existing = await user_has_open_ticket(
            interaction.guild,
            interaction.user.id
        )

        if existing:
            await safe_ephemeral(
                interaction,
                f"Masz już otwarty ticket: {existing.mention}"
            )
            return

        answers = {
            "age": self.age.value,
            "name": self.name.value,
            "minecraft": self.minecraft.value,
            "pvp": self.pvp.value,
            "why": self.why.value
        }

        await create_ticket_after_recruitment(
            interaction,
            answers
        )


# =========================================================
# PANEL W TICKETACH
# =========================================================

class TicketActionView(ui.LayoutView):

    def __init__(
        self,
        ticket_type: str,
        owner_mention: str,
        category_name: str,
        recruitment_answers=None
    ):
        super().__init__(timeout=None)

        container = ui.Container()

        gallery = ui.MediaGallery()
        gallery.add_item(media=TICKET_IMAGE_URL)
        container.add_item(gallery)

        container.add_item(
            ui.TextDisplay(
                content=f"## **{owner_mention} × {category_name}**"
            )
        )

        if ticket_type == "klatki":
            content = f"{ARROW} Czekaj na odpowiedź Liderów"

        elif ticket_type == "rekrutacja":
            a = recruitment_answers or {}

            content = (
                f"{PONNY} **Odpowiedzi:**\n\n"
                f"{ARROW} **Wiek:** {a.get('age', '-')}\n"
                f"{ARROW} **Imię:** {a.get('name', '-')}\n"
                f"{ARROW} **Nick Minecraft:** {a.get('minecraft', '-')}\n"
                f"{ARROW} **Twoje Pvp:** {a.get('pvp', '-')}\n"
                f"{ARROW} **Dlaczego Ponny:** {a.get('why', '-')}"
            )

        else:
            content = (
                f"{ARROW} Opisz dokładnie swoją sprawę. "
                "Osoba z supportu zajmie się Twoim zgłoszeniem "
                "tak szybko, jak to możliwe."
            )

        container.add_item(
            ui.TextDisplay(content=content)
        )

        row = ui.ActionRow()

        row.add_item(CloseTicketButton(ticket_type))
        row.add_item(AddPersonButton())
        row.add_item(RemovePersonButton())

        container.add_item(row)

        self.add_item(container)


# =========================================================
# ZAMKNIJ TICKET
# =========================================================

class CloseTicketButton(ui.Button):

    def __init__(self, ticket_type):
        super().__init__(
            label="ᴢᴀᴍᴋɴɪᴊ ᴛɪᴄᴋᴇᴛ",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_close"
        )

        self.ticket_type = ticket_type

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return

        if not can_close_ticket(
            interaction.user,
            self.ticket_type
        ):
            await safe_ephemeral(
                interaction,
                "Nie masz uprawnień do zamknięcia tego ticketu."
            )
            return

        try:
            await interaction.response.send_message(
                "Czy na pewno chcesz zamknąć ten ticket?",
                view=CloseConfirmView(self.ticket_type),
                ephemeral=True
            )
        except discord.HTTPException as e:
            print(f"[CLOSE RESPONSE ERROR] {e}")


# =========================================================
# POTWIERDZENIE ZAMKNIĘCIA
# =========================================================

class CloseConfirmView(ui.View):

    def __init__(self, ticket_type):
        super().__init__(timeout=60)
        self.ticket_type = ticket_type

    @ui.button(
        label="TAK",
        style=discord.ButtonStyle.secondary
    )
    async def confirm_yes(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not isinstance(interaction.user, discord.Member):
            return

        if not can_close_ticket(
            interaction.user,
            self.ticket_type
        ):
            await safe_ephemeral(
                interaction,
                "Nie masz uprawnień."
            )
            return

        try:
            await interaction.response.edit_message(
                content="Ticket zostanie zamknięty w przeciągu 10 sekund.",
                view=None
            )
        except discord.HTTPException as e:
            print(f"[CLOSE EDIT ERROR] {e}")
            return

        channel = interaction.channel

        await asyncio.sleep(10)

        if not isinstance(channel, discord.TextChannel):
            return

        try:
            await create_transcript(channel)
        except Exception as e:
            print(f"[TRANSCRIPT ERROR] {type(e).__name__}: {e}")

        try:
            await send_owner_transcript_dm(channel)
        except Exception as e:
            print(f"[DM ERROR] {type(e).__name__}: {e}")

        try:
            await channel.delete(reason="Ticket zamknięty")
        except Exception as e:
            print(f"[DELETE ERROR] {type(e).__name__}: {e}")

    @ui.button(
        label="NIE",
        style=discord.ButtonStyle.secondary
    )
    async def confirm_no(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        try:
            await interaction.response.edit_message(
                content="Zamykanie ticketu anulowane.",
                view=None
            )
        except discord.HTTPException as e:
            print(f"[CANCEL ERROR] {e}")


# =========================================================
# DODAJ OSOBĘ
# =========================================================

class AddPersonModal(ui.Modal, title="Dodaj osobę"):

    member_id = ui.TextInput(
        label="ID użytkownika",
        placeholder="Wpisz ID użytkownika Discord...",
        required=True,
        max_length=25
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        try:
            member_id = int(self.member_id.value)
        except ValueError:
            await safe_ephemeral(
                interaction,
                "Nieprawidłowe ID użytkownika."
            )
            return

        member = interaction.guild.get_member(member_id)

        if not member:
            try:
                member = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                member = None

        if not member:
            await safe_ephemeral(
                interaction,
                "Nie znaleziono takiego użytkownika."
            )
            return

        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
        except discord.HTTPException as e:
            print(f"[ADD PERSON ERROR] {e}")
            await safe_ephemeral(
                interaction,
                "Nie udało się dodać użytkownika do ticketu."
            )
            return

        await safe_ephemeral(
            interaction,
            f"Dodano {member.mention} do ticketu."
        )


class AddPersonButton(ui.Button):

    def __init__(self):
        super().__init__(
            label="ᴅᴏᴅᴀᴊ ᴏsᴏʙᴇ̨",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_add_person"
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return

        ticket_type = get_ticket_type_from_channel(
            interaction.channel
        )

        if not can_close_ticket(
            interaction.user,
            ticket_type or "inne"
        ):
            await safe_ephemeral(
                interaction,
                "Nie masz uprawnień do zarządzania tym ticketem."
            )
            return

        try:
            await interaction.response.send_modal(
                AddPersonModal()
            )
        except discord.HTTPException as e:
            print(f"[ADD MODAL ERROR] {e}")


# =========================================================
# USUŃ OSOBĘ
# =========================================================

class RemovePersonModal(ui.Modal, title="Usuń osobę"):

    member_id = ui.TextInput(
        label="ID użytkownika",
        placeholder="Wpisz ID użytkownika Discord...",
        required=True,
        max_length=25
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        try:
            member_id = int(self.member_id.value)
        except ValueError:
            await safe_ephemeral(
                interaction,
                "Nieprawidłowe ID użytkownika."
            )
            return

        owner_id = get_ticket_owner_id(channel)

        if member_id == owner_id:
            await safe_ephemeral(
                interaction,
                "Nie możesz usunąć właściciela ticketu."
            )
            return

        member = interaction.guild.get_member(member_id)

        if not member:
            try:
                member = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                member = None

        if not member:
            await safe_ephemeral(
                interaction,
                "Nie znaleziono takiego użytkownika."
            )
            return

        try:
            await channel.set_permissions(
                member,
                overwrite=None
            )
        except discord.HTTPException as e:
            print(f"[REMOVE PERSON ERROR] {e}")
            await safe_ephemeral(
                interaction,
                "Nie udało się usunąć użytkownika z ticketu."
            )
            return

        await safe_ephemeral(
            interaction,
            f"Usunięto {member.mention} z ticketu."
        )


class RemovePersonButton(ui.Button):

    def __init__(self):
        super().__init__(
            label="ᴜsᴜɴ́ ᴏsᴏʙᴇ̨",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_remove_person"
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return

        ticket_type = get_ticket_type_from_channel(
            interaction.channel
        )

        if not can_close_ticket(
            interaction.user,
            ticket_type or "inne"
        ):
            await safe_ephemeral(
                interaction,
                "Nie masz uprawnień do zarządzania tym ticketem."
            )
            return

        try:
            await interaction.response.send_modal(
                RemovePersonModal()
            )
        except discord.HTTPException as e:
            print(f"[REMOVE MODAL ERROR] {e}")


# =========================================================
# TWORZENIE UPRAWNIEŃ
# =========================================================

def build_ticket_overwrites(
    guild: discord.Guild,
    member: discord.Member,
    ticket_type: str
):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        )
    }

    support_permissions = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        manage_messages=True,
        attach_files=True,
        embed_links=True
    )

    universal_role = guild.get_role(
        UNIVERSAL_SUPPORT_ROLE_ID
    )

    if universal_role:
        overwrites[universal_role] = support_permissions

    general_role = guild.get_role(
        GENERAL_SUPPORT_ROLE_ID
    )

    if general_role:
        overwrites[general_role] = support_permissions

    if ticket_type == "rekrutacja":
        recruitment_role = guild.get_role(
            RECRUITMENT_ROLE_ID
        )

        if recruitment_role:
            overwrites[recruitment_role] = support_permissions

    return overwrites


# =========================================================
# TWORZENIE TICKETU
# =========================================================

async def create_ticket(
    interaction: discord.Interaction,
    ticket_type: str
):
    guild = interaction.guild

    if guild is None:
        return

    existing = await user_has_open_ticket(
        guild,
        interaction.user.id
    )

    if existing:
        await safe_ephemeral(
            interaction,
            f"Masz już otwarty ticket: {existing.mention}"
        )
        return

    category = guild.get_channel(
        TICKET_CATEGORY_ID
    )

    if not isinstance(category, discord.CategoryChannel):
        await safe_ephemeral(
            interaction,
            "Nie znaleziono kategorii ticketów."
        )
        return

    member = interaction.user

    overwrites = build_ticket_overwrites(
        guild,
        member,
        ticket_type
    )

    topic = (
        f"ticket_type={ticket_type}"
        f"|owner_id={member.id}"
    )

    try:
        channel = await guild.create_text_channel(
            name=ticket_name(member, ticket_type),
            category=category,
            overwrites=overwrites,
            topic=topic,
            reason="Utworzenie ticketu"
        )
    except discord.HTTPException as e:
        print(f"[CREATE TICKET ERROR] {e}")
        await safe_ephemeral(
            interaction,
            "Nie udało się utworzyć ticketu. Spróbuj ponownie za chwilę."
        )
        return

    await safe_ephemeral(
        interaction,
        f"Ticket został utworzony: {channel.mention}"
    )

    try:
        await channel.send(
            content=member.mention,
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=False,
                everyone=False
            )
        )

        category_names = {
            "klatki": "Klatki",
            "rekrutacja": "Rekrutacja",
            "inne": "Inne"
        }

        await channel.send(
            view=TicketActionView(
                ticket_type=ticket_type,
                owner_mention=member.mention,
                category_name=category_names[ticket_type]
            )
        )
    except discord.HTTPException as e:
        print(f"[TICKET MESSAGE ERROR] {e}")


# =========================================================
# REKRUTACJA PO MODALU
# =========================================================

async def create_ticket_after_recruitment(
    interaction: discord.Interaction,
    answers: dict
):
    guild = interaction.guild

    if guild is None:
        return

    existing = await user_has_open_ticket(
        guild,
        interaction.user.id
    )

    if existing:
        await safe_ephemeral(
            interaction,
            f"Masz już otwarty ticket: {existing.mention}"
        )
        return

    category = guild.get_channel(
        TICKET_CATEGORY_ID
    )

    if not isinstance(category, discord.CategoryChannel):
        await safe_ephemeral(
            interaction,
            "Nie znaleziono kategorii ticketów."
        )
        return

    member = interaction.user

    overwrites = build_ticket_overwrites(
        guild,
        member,
        "rekrutacja"
    )

    topic = (
        "ticket_type=rekrutacja"
        f"|owner_id={member.id}"
    )

    try:
        channel = await guild.create_text_channel(
            name=ticket_name(member, "rekrutacja"),
            category=category,
            overwrites=overwrites,
            topic=topic,
            reason="Utworzenie ticketu rekrutacyjnego"
        )
    except discord.HTTPException as e:
        print(f"[CREATE RECRUITMENT ERROR] {e}")
        await safe_ephemeral(
            interaction,
            "Nie udało się utworzyć ticketu rekrutacyjnego."
        )
        return

    await safe_ephemeral(
        interaction,
        f"Ticket rekrutacyjny został utworzony: {channel.mention}"
    )

    try:
        await channel.send(
            content=member.mention,
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=False,
                everyone=False
            )
        )

        await channel.send(
            view=TicketActionView(
                ticket_type="rekrutacja",
                owner_mention=member.mention,
                category_name="Rekrutacja",
                recruitment_answers=answers
            )
        )
    except discord.HTTPException as e:
        print(f"[RECRUITMENT MESSAGE ERROR] {e}")


# =========================================================
# TRANSCRIPT
# =========================================================

async def create_transcript(channel: discord.TextChannel):
    transcript_channel = channel.guild.get_channel(
        TRANSCRIPT_CHANNEL_ID
    )

    if not isinstance(
        transcript_channel,
        discord.TextChannel
    ):
        print("[TRANSCRIPT] Nie znaleziono kanału transcriptów.")
        return None

    messages = []

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):
        messages.append(message)

    owner_id = get_ticket_owner_id(channel)
    ticket_type = get_ticket_type_from_channel(channel)

    owner = None

    if owner_id:
        owner = channel.guild.get_member(owner_id)

        if owner is None:
            try:
                owner = await channel.guild.fetch_member(owner_id)
            except discord.HTTPException:
                owner = None

    ticket_type_name = {
        "klatki": "Klatki",
        "rekrutacja": "Rekrutacja",
        "inne": "Inne"
    }.get(ticket_type, "Ticket")

    rows = []

    for message in messages:
        timestamp = message.created_at.strftime(
            "%d.%m.%Y %H:%M"
        )

        author_name = html.escape(
            message.author.display_name
        )

        author_avatar = (
            str(message.author.display_avatar.url)
            if message.author.display_avatar
            else ""
        )

        content = html.escape(
            message.content or ""
        ).replace("\n", "<br>")

        attachments_html = ""

        for attachment in message.attachments:
            url = html.escape(
                attachment.url,
                quote=True
            )

            filename = html.escape(
                attachment.filename
            )

            attachments_html += (
                '<div class="attachment">'
                f'<a href="{url}" target="_blank">'
                f'📎 {filename}'
                '</a>'
                '</div>'
            )

        embeds_html = ""

        for embed in message.embeds:
            embed_parts = []

            if embed.title:
                embed_parts.append(
                    '<div class="embed-title">'
                    f'{html.escape(embed.title)}'
                    '</div>'
                )

            if embed.description:
                embed_parts.append(
                    '<div class="embed-description">'
                    f'{html.escape(embed.description)}'
                    '</div>'
                )

            for field in embed.fields:
                embed_parts.append(
                    '<div class="embed-field">'
                    f'<strong>{html.escape(field.name)}</strong>'
                    '<br>'
                    f'{html.escape(field.value)}'
                    '</div>'
                )

            embed_html = '<div class="discord-embed">'

            if embed.author and embed.author.name:
                embed_html += (
                    '<div class="embed-author">'
                    f'{html.escape(embed.author.name)}'
                    '</div>'
                )

            embed_html += "".join(embed_parts)

            if embed.image and embed.image.url:
                embed_html += (
                    '<img class="embed-image" '
                    f'src="{html.escape(embed.image.url, quote=True)}">'
                )

            if embed.thumbnail and embed.thumbnail.url:
                embed_html += (
                    '<img class="embed-thumbnail" '
                    f'src="{html.escape(embed.thumbnail.url, quote=True)}">'
                )

            if embed.footer and embed.footer.text:
                embed_html += (
                    '<div class="embed-footer">'
                    f'{html.escape(embed.footer.text)}'
                    '</div>'
                )

            embed_html += "</div>"
            embeds_html += embed_html

        rows.append(
            f"""
            <div class="message">
                <img class="avatar" src="{html.escape(author_avatar, quote=True)}">

                <div class="message-content">
                    <div class="message-header">
                        <span class="author">{author_name}</span>
                        <span class="time">{timestamp}</span>
                    </div>

                    <div class="text">
                        {content}
                    </div>

                    {attachments_html}
                    {embeds_html}
                </div>
            </div>
            """
        )

    owner_display = (
        owner.display_name
        if owner
        else "Nieznany"
    )

    created_at = channel.created_at.strftime(
        "%d.%m.%Y %H:%M"
    )

    closed_at = datetime.now().strftime(
        "%d.%m.%Y %H:%M"
    )

    transcript_html = f"""
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Transcript - {html.escape(channel.name)}</title>

<style>
* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #0d0d12;
    color: #f5f5f7;
    font-family: Arial, Helvetica, sans-serif;
}}

.loader {{
    position: fixed;
    inset: 0;
    background: #0d0d12;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    animation: fadeOut 2.5s ease forwards;
    animation-delay: 2s;
}}

.loader img {{
    width: 300px;
    height: 300px;
    object-fit: contain;
    animation: rotate 2s linear infinite;
}}

@keyframes rotate {{
    from {{
        transform: rotate(0deg);
    }}
    to {{
        transform: rotate(360deg);
    }}
}}

@keyframes fadeOut {{
    0% {{
        opacity: 1;
        visibility: visible;
    }}
    70% {{
        opacity: 1;
    }}
    100% {{
        opacity: 0;
        visibility: hidden;
    }}
}}

.header {{
    padding: 35px 20px;
    text-align: center;
}}

.header h1 {{
    margin: 0 0 10px;
    font-size: 30px;
}}

.header p {{
    margin: 5px 0;
    color: #aaa;
}}

.messages {{
    width: min(1000px, 95%);
    margin: auto;
    padding-bottom: 50px;
}}

.message {{
    display: flex;
    gap: 14px;
    padding: 15px;
    margin-bottom: 10px;
    background: #15151d;
    border-radius: 12px;
}}

.avatar {{
    width: 42px;
    height: 42px;
    border-radius: 50%;
    object-fit: cover;
}}

.message-content {{
    flex: 1;
    min-width: 0;
}}

.message-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}

.author {{
    font-weight: 700;
}}

.time {{
    color: #777;
    font-size: 12px;
}}

.text {{
    color: #ddd;
    line-height: 1.5;
    overflow-wrap: anywhere;
}}

.attachment {{
    margin-top: 8px;
}}

.attachment a {{
    color: #ff9fd3;
    text-decoration: none;
}}

.discord-embed {{
    margin-top: 10px;
    padding: 14px;
    background: #202028;
    border-left: 4px solid #ff8fc9;
    border-radius: 7px;
}}

.embed-title {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 8px;
}}

.embed-description {{
    line-height: 1.5;
}}

.embed-field {{
    margin-top: 10px;
}}

.embed-author {{
    font-weight: 700;
    margin-bottom: 8px;
}}

.embed-image {{
    max-width: 100%;
    border-radius: 6px;
    margin-top: 12px;
}}

.embed-thumbnail {{
    max-width: 120px;
    border-radius: 6px;
    margin-top: 12px;
}}

.embed-footer {{
    margin-top: 12px;
    color: #888;
    font-size: 12px;
}}

.info {{
    width: min(1000px, 95%);
    margin: 0 auto 25px;
    padding: 18px;
    background: #15151d;
    border-radius: 12px;
}}
</style>
</head>

<body>

<div class="loader">
    <img src="{html.escape(TRANSCRIPT_LOADING_IMAGE, quote=True)}">
</div>

<div class="header">
    <h1>Transcript — {html.escape(channel.name)}</h1>
    <p>Ticket: {html.escape(ticket_type_name)}</p>
</div>

<div class="info">
    <strong>Właściciel:</strong>
    {html.escape(owner_display)}
    <br>
    <strong>Utworzono:</strong>
    {created_at}
    <br>
    <strong>Zamknięto:</strong>
    {closed_at}
</div>

<div class="messages">
    {''.join(rows)}
</div>

</body>
</html>
"""

    safe_channel_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in channel.name
    )

    filename = f"transcript-{safe_channel_name}.html"

    os.makedirs("transcripts", exist_ok=True)

    filepath = os.path.join(
        "transcripts",
        filename
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(transcript_html)

    file = discord.File(
        filepath,
        filename=filename
    )

    try:
        message = await transcript_channel.send(
            content=(
                f"📄 **Transcript:** `{channel.name}`\n"
                f"👤 **Właściciel:** "
                f"{owner.mention if owner else owner_display}\n"
                f"📁 **Kategoria:** {ticket_type_name}"
            ),
            file=file,
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=False,
                everyone=False
            )
        )
    except discord.HTTPException as e:
        print(f"[TRANSCRIPT SEND ERROR] {e}")
        return None

    return message, filepath


# =========================================================
# TRANSCRIPT DOWNLOAD
# =========================================================

class TranscriptDownloadView(discord.ui.View):

    def __init__(self, url: str):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Pobierz transcript",
                style=discord.ButtonStyle.link,
                url=url
            )
        )


async def send_owner_transcript_dm(
    channel: discord.TextChannel
):
    owner_id = get_ticket_owner_id(channel)

    if not owner_id:
        return

    owner = channel.guild.get_member(owner_id)

    if owner is None:
        try:
            owner = await channel.guild.fetch_member(owner_id)
        except discord.HTTPException:
            return

    if owner is None:
        return

    transcript_channel = channel.guild.get_channel(
        TRANSCRIPT_CHANNEL_ID
    )

    if not isinstance(
        transcript_channel,
        discord.TextChannel
    ):
        return

    messages = [
        message
        async for message in transcript_channel.history(limit=20)
    ]

    transcript_message = None

    for message in messages:
        if (
            bot.user
            and message.author.id == bot.user.id
            and message.attachments
            and channel.name in message.content
        ):
            transcript_message = message
            break

    if transcript_message is None:
        print(
            f"[DM] Nie znaleziono transcriptu dla {channel.name}"
        )
        return

    attachment = transcript_message.attachments[0]

    try:
        await owner.send(
            content=(
                "💗 **Twój ticket został zamknięty.**\n\n"
                "Poniżej znajdziesz transcript rozmowy."
            ),
            view=TranscriptDownloadView(
                attachment.url
            )
        )
    except discord.Forbidden:
        print(
            f"[DM] Nie można wysłać DM do {owner}."
        )
    except discord.HTTPException as e:
        print(
            f"[DM ERROR] {e}"
        )


# =========================================================
# POWITANIA
# =========================================================

async def send_welcome(member: discord.Member):
    channel = member.guild.get_channel(
        WELCOME_CHANNEL_ID
    )

    if not isinstance(
        channel,
        discord.TextChannel
    ):
        print(
            f"[WELCOME] Nie znaleziono kanału "
            f"{WELCOME_CHANNEL_ID}"
        )
        return

    container = ui.Container()

    gallery = ui.MediaGallery()
    gallery.add_item(media=WELCOME_IMAGE_URL)
    container.add_item(gallery)

    member_count = member.guild.member_count or 0

    welcome_text = (
        "# ```🦄 GILDIA PONNY × WITAMY```\n"
        f"> {ARROW} Witaj {member.mention}\n"
        f"> {ARROW} Jesteś **{member_count}** na naszym serwerze\n\n"
        f"> {ARROW} Mamy nadzieję, że zostaniesz z nami na dłużej."
    )

    container.add_item(
        ui.TextDisplay(content=welcome_text)
    )

    view = ui.LayoutView(timeout=None)
    view.add_item(container)

    await channel.send(
        view=view,
        allowed_mentions=discord.AllowedMentions(
            users=True,
            roles=False,
            everyone=False
        )
    )


# =========================================================
# NOWY CZŁONEK
# =========================================================

@bot.event
async def on_member_join(member: discord.Member):
    try:
        await send_welcome(member)
    except Exception as e:
        print(
            f"[WELCOME ERROR] {type(e).__name__}: {e}"
        )


# =========================================================
# AUTOMATYCZNY PANEL
# =========================================================

async def ensure_ticket_panel():
    async with panel_lock:
        channel = bot.get_channel(
            TICKET_PANEL_CHANNEL_ID
        )

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            print(
                "[TICKET PANEL] Nie znaleziono kanału."
            )
            return

        saved_id = load_panel_message_id()

        if saved_id:
            try:
                message = await channel.fetch_message(
                    saved_id
                )

                if (
                    message
                    and bot.user
                    and message.author.id == bot.user.id
                ):
                    print(
                        "[TICKET PANEL] Panel już istnieje."
                    )
                    return

            except discord.NotFound:
                pass

            except discord.HTTPException as e:
                print(
                    f"[TICKET PANEL] Błąd sprawdzania panelu: {e}"
                )
                return

        # Jeżeli panelu nie ma, tworzymy dokładnie jeden.
        try:
            message = await channel.send(
                view=TicketPanelView()
            )

            save_panel_message_id(message.id)

            print(
                f"[TICKET PANEL] Utworzono panel: {message.id}"
            )

        except discord.HTTPException as e:
            print(
                f"[TICKET PANEL ERROR] {e}"
            )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():
    global views_registered

    print(
        f"Zalogowano jako {bot.user} "
        f"(ID: {bot.user.id})"
    )

    await set_bot_status()

    if not views_registered:
        bot.add_view(TicketPanelView())

        bot.add_view(
            TicketActionView(
                ticket_type="inne",
                owner_mention="@user",
                category_name="Inne"
            )
        )

        views_registered = True

    await ensure_ticket_panel()

    print("Bot jest gotowy.")


# =========================================================
# BŁĘDY INTERAKCJI
# =========================================================

@bot.event
async def on_error(event, *args, **kwargs):
    print(
        f"[BOT EVENT ERROR] event={event}"
    )


# =========================================================
# FLASK / RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Discord działa!", 200


@app.route("/health")
def health():
    return "OK", 200


def run_web():
    port = int(
        os.environ.get("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    server = Thread(
        target=run_web,
        daemon=True
    )
    server.start()


# =========================================================
# START
# =========================================================

keep_alive()

if __name__ == "__main__":
    bot.run(TOKEN)
