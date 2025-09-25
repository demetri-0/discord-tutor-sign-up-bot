import os, re, secrets
from typing import Dict, List
import discord
from discord import app_commands
from discord.ext import commands
import json
from pathlib import Path

_GUILD_ID = os.getenv("GUILD_ID")
_GUILD = discord.Object(id=int(_GUILD_ID)) if (_GUILD_ID and _GUILD_ID.isdigit()) else None

MAX_COURSES = 25

# ---------- tiny helpers ----------
_course_header_re = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9 \-]*)\s*(?:\|\s*Prof:\s*(.+))?\s*$')

def parse_courses(raw: str) -> Dict[str, Dict]:
    """Option A: blocks separated by blank lines. First line 'COURSE | Prof: NAME' (prof optional); following lines are topics."""
    blocks = [b for b in re.split(r'\n\s*\n', raw.strip()) if b.strip()]
    out: Dict[str, Dict] = {}
    for blk in blocks[:MAX_COURSES]:
        lines = [l.strip() for l in blk.splitlines() if l.strip()]
        if not lines: continue
        m = _course_header_re.match(lines[0])
        if not m:  # skip bad blocks
            continue
        course = m.group(1).upper().strip()
        prof = (m.group(2) or "").strip()
        topics = []
        seen = set()
        for line in lines[1:]:
            if line not in seen:
                topics.append(line)
                seen.add(line)
        if course in out:
            # merge topics if duplicate course appears
            for t in topics:
                if t not in out[course]["desc"]:
                    out[course]["desc"].append(t)
        else:
            out[course] = {"professor": prof, "desc": topics, "volunteers": []}
    return out

def slugify(course: str) -> str:
    return re.sub(r'[^A-Z0-9]+', '-', course.upper()).strip('-')[:80]

# ---------- UI components ----------
class VolunteerButton(discord.ui.Button):
    def __init__(self, cog: "Study", message_id: int, course: str, professor: str):
        self.cog = cog
        self.message_id = message_id
        self.course = course
        cid = f"tt;{message_id};{slugify(course)}"
        label_text = f"{course}" + (f" ({professor})" if professor else "")

        super().__init__(label=label_text, style=discord.ButtonStyle.primary, custom_id=cid)

    async def callback(self, interaction: discord.Interaction):
        sess = self.cog.sessions.get(self.message_id)
        if not sess:
            await interaction.response.send_message("Sorry, this session data wasn't found.", ephemeral=True)
            return
        c = sess["courses"].get(self.course)
        if not c:
            await interaction.response.send_message("Course not found.", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid in c["volunteers"]:
            c["volunteers"].remove(uid)
            msg = "Removed you as a tutor from this course."
        else:
            c["volunteers"].append(uid)
            msg = "Added you as a tutor for this course."
        # Confirm to the clicker
        await interaction.response.send_message(msg, ephemeral=True)
        self.cog._save_sessions()
        # Refresh the posted message
        embed = self.cog.build_embed(sess, guild=interaction.guild)
        try:
            await interaction.message.edit(embed=embed, view=self.view)
        except discord.HTTPException:
            pass

class CourseView(discord.ui.View):
    def __init__(self, cog: "Study", message_id: int, courses: dict):
        super().__init__(timeout=None)  # (persistence to be added later)
        for course_name in list(courses.keys())[:MAX_COURSES]:
            self.add_item(VolunteerButton(cog, message_id, course_name, courses[course_name]["professor"]))

class PreviewView(discord.ui.View):
    def __init__(self, cog: "Study", token: str):
        super().__init__(timeout=600)
        self.cog = cog
        self.token = token

    @discord.ui.button(label="Post", style=discord.ButtonStyle.success)
    async def post(self, interaction: discord.Interaction, _button: discord.ui.Button):
        data = self.cog.previews.get(self.token)
        if not data or data["user_id"] != interaction.user.id:
            await interaction.response.send_message("This preview isn't yours or expired.", ephemeral=True)
            return
        # Send the real message first (no view) to get message_id
        embed = self.cog.build_embed({"announcement": data["announcement"],
                                      "courses": data["courses"]}, guild=None)
        msg = await interaction.channel.send(embed=embed)
        # Save session in-memory
        session = {
            "message_id": msg.id,
            "channel_id": str(msg.channel.id),
            "guild_id": str(msg.guild.id) if msg.guild else "",
            "announcement": data["announcement"],
            "courses": data["courses"],  # already includes volunteers arrays
        }
        self.cog.sessions[msg.id] = session
        self.cog._save_sessions()
        # Attach buttons per course
        view = CourseView(self.cog, msg.id, dict(session["courses"]))
        await msg.edit(view=view)
        # Ack to the poster
        await interaction.response.send_message(f"Posted! Jump: {msg.jump_url}", ephemeral=True)
        # cleanup preview
        self.cog.previews.pop(self.token, None)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, _button: discord.ui.Button):
        data = self.cog.previews.get(self.token)
        if not data or data["user_id"] != interaction.user.id:
            await interaction.response.send_message("This preview isn't yours or expired.", ephemeral=True)
            return
        await interaction.response.send_modal(StudySetupModal(self.cog,
                                                              announcement_default=data["announcement"],
                                                              courses_default=data["raw_courses"]))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.cog.previews.pop(self.token, None)
        await interaction.response.send_message("Canceled preview.", ephemeral=True)

# ---------- Modal ----------
class StudySetupModal(discord.ui.Modal):
    def __init__(self, cog: "Study",
                 *, announcement_default: str = "", courses_default: str = ""):
        super().__init__(title="Study Tables Setup")
        self.cog = cog

        # safe defaults
        announcement_default = (announcement_default or "").strip()[:500]
        courses_default = (courses_default or "").strip()[:3500]

        self.session_announcement_input = discord.ui.TextInput(
            label="Study Tables Announcement",
            style=discord.TextStyle.paragraph,
            default=announcement_default or "Study Tables will be held on {date} at {place}.\n\nBrothers need help with the courses listed below.\nIf you are able to tutor during Study Tables, please click the corresponding toggle button.\n\nIf you requested help, find a brother that is listed as a tutor for your course during Study Tables.",
            required=True, max_length=500,
        )
        self.courses_input = discord.ui.TextInput(
            label="Courses (MUST FOLLOW THIS EXACT FORMAT)",
            style=discord.TextStyle.paragraph,
            default=courses_default or
            "MECH-241 | Prof: Dr. Smith\nAssignment 1\nQuiz 2\n\nCHEM-132\nReaction rates",
            required=True, max_length=3500,
        )

        self.add_item(self.session_announcement_input)
        self.add_item(self.courses_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Parse courses
        courses = parse_courses(self.courses_input.value)
        if not courses:
            await interaction.response.send_message(
                "I couldn't parse any courses. Make sure each block starts with `COURSE | Prof: NAME` (prof optional).",
                ephemeral=True
            )
            return

        # Build preview + cache it
        token = secrets.token_urlsafe(8)
        self.cog.previews[token] = {
            "user_id": interaction.user.id,
            "channel_id": interaction.channel.id if interaction.channel else None,
            "announcement": self.session_announcement_input.value.strip(),
            "courses": courses,
            "raw_courses": self.courses_input.value.strip(),
        }

        embed = self.cog.build_embed({
            "announcement": self.session_announcement_input.value.strip(),
            "courses": courses
        }, guild=None)

        await interaction.response.send_message(
            content="**Preview (only you can see this):**",
            embed=embed,
            view=PreviewView(self.cog, token),
            ephemeral=True
        )

# ---------- Cog ----------
DATA_PATH = Path("data/sessions.json")

class Study(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[int, Dict] = {}   # message_id -> session (in-memory for now)
        self.previews: Dict[str, Dict] = {}   # token -> preview data
        self._reattached = False
        self._load_sessions()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.reattach_persistent_views()

    def _load_sessions(self):
        if DATA_PATH.exists():
            try:
                raw = json.load(DATA_PATH.open("r", encoding="utf-8"))
                # file stores keys as strings; convert to ints in-memory
                self.sessions = {int(k): v for k, v in (raw.get("sessions") or {}).items()}
            except Exception:
                self.sessions = {}
        else:
            self.sessions = {}

    def _save_sessions(self):
        # store keys as strings for JSON
        serializable = {"sessions": {str(k): v for k, v in self.sessions.items()}}
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATA_PATH.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    def build_embed(self, session: Dict, guild: discord.Guild | None) -> discord.Embed:
        """Render the announcement + courses + current volunteers into an embed."""

        EQUALS_SEP = "=" * 30     # U+FF0A FULLWIDTH ASTERISK
        DASH_SEP = "-" * 30     # U+2500 BOX DRAWINGS LIGHT HORIZONTAL

        description = session.get("announcement", "").strip() + f"\n\n{EQUALS_SEP}"
        embed = discord.Embed(title="Study Tables Preparation", description=description)

        for i in range(len(session["courses"].items())):
            course_name = list(session["courses"].keys())[i]
            data = session["courses"][course_name]

            prof = data.get("professor") or ""
            topics = data.get("desc") or []
            vols = data.get("volunteers") or []
            if guild:
                names = []
                for uid in vols:
                    m = guild.get_member(int(uid))
                    names.append(m.display_name if m else f"User {uid}")
                tutors = "\n".join(names) if names else "—"
            else:
                tutors = "—"
            bullet = "\n".join(f"• {t}" for t in topics) if topics else "_(no specific topics requested)_"
            name = f"{course_name}" + (f" — {prof}" if prof else "")

            value = f"{bullet}\n\n**Tutors:**\n{tutors}"
            if (i == len(session["courses"].items()) - 1):
                value += f"\n\n{EQUALS_SEP}"
            else:
                value += f"\n\n{DASH_SEP}"
            
            embed.add_field(name=name, value=value, inline=False)

        return embed
    
    async def reattach_persistent_views(self):
        if self._reattached:
            return
        # Recreate a persistent view for each saved message/session
        for message_id, sess in self.sessions.items():
            courses = dict(sess.get("courses", {}))
            if not courses:
                continue
            view = CourseView(self, message_id, courses)
            # This attaches the view to existing messages by custom_id (no fetch needed)
            self.bot.add_view(view)
        self._reattached = True

    @app_commands.command(name="tutoring", description="Open the Study Tables setup modal")
    @app_commands.guilds(_GUILD) if _GUILD else (lambda f: f)
    async def study_setup(self, interaction: discord.Interaction):
        await interaction.response.send_modal(StudySetupModal(self))

async def setup(bot: commands.Bot):
    await bot.add_cog(Study(bot))
