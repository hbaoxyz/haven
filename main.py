import os, json, sqlite3, asyncio, logging, io, re
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import discord
from discord.ext import commands, tasks
from config import (DISCORD_TOKEN, DATABASE_PATH, BACKUP_MINUTES as CONFIG_BACKUP_MINUTES, ARCHIVE_DAYS as CONFIG_ARCHIVE_DAYS, LOG_CHANNEL_ID as CONFIG_LOG_CHANNEL_ID, DASHBOARD_KEY as CONFIG_DASHBOARD_KEY, MENU_GIF_URL, HELP_GIF_URL)
from aiohttp import web

TOKEN=os.getenv("DISCORD_TOKEN") or DISCORD_TOKEN
PREFIX='?'
DB=os.getenv("DATABASE_PATH") or DATABASE_PATH
os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
BACKUP_MINUTES=max(5,int(CONFIG_BACKUP_MINUTES))
ARCHIVE_DAYS=max(1,int(CONFIG_ARCHIVE_DAYS))
LOG_CHANNEL_ID=int(CONFIG_LOG_CHANNEL_ID)
PORT=int(os.getenv('PORT','8080'))
DASHBOARD_KEY=CONFIG_DASHBOARD_KEY
logging.basicConfig(level=logging.INFO)
log=logging.getLogger('all4u')
intents=discord.Intents.default()
intents.message_content=True
intents.members=True
intents.guilds=True
intents.moderation=True
bot=commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None, allowed_mentions=discord.AllowedMentions.none())
conn=sqlite3.connect(DB,check_same_thread=False)
conn.execute('PRAGMA journal_mode=WAL')
conn.executescript('''CREATE TABLE IF NOT EXISTS settings(guild INTEGER,key TEXT,value TEXT,PRIMARY KEY(guild,key));
CREATE TABLE IF NOT EXISTS backups(id INTEGER PRIMARY KEY AUTOINCREMENT,guild INTEGER,created TEXT,data TEXT);
CREATE TABLE IF NOT EXISTS messages(guild INTEGER,channel INTEGER,message INTEGER PRIMARY KEY,author INTEGER,author_name TEXT,content TEXT,created TEXT);
CREATE INDEX IF NOT EXISTS messages_guild_idx ON messages(guild,channel,created);
CREATE TABLE IF NOT EXISTS trusted(guild INTEGER,user INTEGER,PRIMARY KEY(guild,user));
CREATE TABLE IF NOT EXISTS warnings(id INTEGER PRIMARY KEY AUTOINCREMENT,guild INTEGER,user INTEGER,moderator INTEGER,reason TEXT,created TEXT);''')
conn.executescript("""CREATE TABLE IF NOT EXISTS recovery_jobs(guild INTEGER PRIMARY KEY,status TEXT,created TEXT,details TEXT);
CREATE TABLE IF NOT EXISTS antibot_allow(guild INTEGER,bot_id INTEGER,PRIMARY KEY(guild,bot_id));""")
conn.commit()
spam=defaultdict(deque)
raid=defaultdict(deque)
LINK_RE=re.compile(r"(?:https?://|www\.|discord\.gg/|discord(?:app)?\.com/invite/)[^\s<>]+",re.I)
SECURITY_KEYS=("antinuke","antiraid","antispam","antilink","raidmode","antibot")
OWNER_ID=731742317010223154
MENU_GIF=MENU_GIF_URL.strip()
HELP_GIF=HELP_GIF_URL.strip()
ASSETS_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

def gif_attachment(kind):
    path=os.path.join(ASSETS_DIR, f'{kind}.gif')
    if not os.path.isfile(path):
        log.error('Missing GIF asset: %s', path)
        return None
    return discord.File(path, filename=f'{kind}.gif')

SECURITY_NAMES={"antinuke":"Anti-Nuke","antiraid":"Anti-Raid","antispam":"Anti-Spam","antilink":"Anti-Link","raidmode":"Raid Mode","antibot":"Anti-Rogue Bot"}

def save_setting(g,k,value):
    conn.execute("INSERT OR REPLACE INTO settings(guild,key,value) VALUES(?,?,?)",(g,k,value));conn.commit()

def security_embed(g):
    e=discord.Embed(title="🛡️ 𝙃𝙤𝙖𝙣𝙜 𝙏𝙪 𝙈𝙪𝙖 𝘿𝙤𝙣𝙜",description="Chọn nút bên dưới để bật/tắt bảo vệ máy chủ.\n🟢 Bật  •  🔴 Tắt",color=discord.Color.blurple())
    for k in SECURITY_KEYS:
        e.add_field(name=SECURITY_NAMES[k],value="🟢 ON" if enabled(g.id,k) else "🔴 OFF",inline=True)
    e.set_image(url=MENU_GIF or 'attachment://menu.gif')
    e.set_footer(text="Chỉ quản trị viên có quyền Manage Server được thay đổi • Dữ liệu được lưu tự động")
    return e

class SecurityView(discord.ui.View):
    def __init__(self,guild_id):
        super().__init__(timeout=None)
        self.guild_id=guild_id
    async def change(self,interaction,key):
        if not interaction.guild or interaction.guild.id!=self.guild_id:
            return await interaction.response.send_message("Menu này thuộc máy chủ khác.",ephemeral=False)
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("⛔ Cần quyền Manage Server để đổi cài đặt.",ephemeral=False)
        save_setting(self.guild_id,key,"off" if enabled(self.guild_id,key) else "on")
        await interaction.response.edit_message(embed=security_embed(interaction.guild),view=self)
    @discord.ui.button(label="Anti-Nuke",emoji="🛡️",style=discord.ButtonStyle.secondary,custom_id="all4u:antinuke")
    async def nuke(self,i,b):await self.change(i,"antinuke")
    @discord.ui.button(label="Anti-Raid",emoji="🚨",style=discord.ButtonStyle.secondary,custom_id="all4u:antiraid")
    async def anti_raid(self,i,b):await self.change(i,"antiraid")
    @discord.ui.button(label="Anti-Spam",emoji="💬",style=discord.ButtonStyle.secondary,custom_id="all4u:antispam")
    async def anti_spam(self,i,b):await self.change(i,"antispam")
    @discord.ui.button(label="Anti-Link",emoji="🔗",style=discord.ButtonStyle.secondary,custom_id="all4u:antilink")
    async def anti_link(self,i,b):await self.change(i,"antilink")
    @discord.ui.button(label="Raid Mode",emoji="🔒",style=discord.ButtonStyle.danger,custom_id="all4u:raidmode")
    async def raid_mode(self,i,b):await self.change(i,"raidmode")

@bot.command(name="menu")
@commands.guild_only()
async def menu(ctx):
    await ctx.send(embed=security_embed(ctx.guild),view=SecurityView(ctx.guild.id),file=gif_attachment('menu') if not MENU_GIF else None)



def setting(g,k,default='off'):
    row=conn.execute('SELECT value FROM settings WHERE guild=? AND key=?',(g,k)).fetchone()
    return row[0] if row else default

def enabled(g,k): return setting(g,k)=='on'

def trusted(g,u):
    return bool(conn.execute('SELECT 1 FROM trusted WHERE guild=? AND user=?',(g,u)).fetchone())

async def notify(guild,text):
    channel=guild.get_channel(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None
    if channel is None:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel=ch;break
    if channel:
        try: await channel.send(text[:1900],allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException: pass

async def make_backup(guild):
    data={'guild_name':guild.name,'roles':[], 'categories':[], 'channels':[]}
    for role in guild.roles:
        if role.is_default() or role.managed: continue
        data['roles'].append({'name':role.name,'color':role.color.value,'hoist':role.hoist,'mentionable':role.mentionable,'permissions':role.permissions.value,'position':role.position})
    for category in guild.categories:
        data['categories'].append({'name':category.name,'position':category.position})
    for channel in guild.channels:
        if isinstance(channel,discord.CategoryChannel): continue
        kind='text' if isinstance(channel,discord.TextChannel) else 'voice' if isinstance(channel,discord.VoiceChannel) else 'other'
        data['channels'].append({'name':channel.name,'type':kind,'category':channel.category.name if channel.category else None,'position':channel.position,'topic':getattr(channel,'topic',None),'nsfw':getattr(channel,'nsfw',False)})
    conn.execute('INSERT INTO backups(guild,created,data) VALUES(?,?,?)',(guild.id,datetime.now(timezone.utc).isoformat(),json.dumps(data,ensure_ascii=False)))
    conn.commit()
    return data

@bot.event
async def on_ready():
    log.info('All4u online as %s',bot.user)
    for kind in ('menu','help','backup'):
        path=os.path.join(ASSETS_DIR, f'{kind}.gif')
        log.info('GIF %s: %s', kind, 'FOUND' if os.path.isfile(path) else 'MISSING')
    if not getattr(bot,'_all4u_views_registered',False):
        for g in bot.guilds:bot.add_view(SecurityView(g.id))
        bot._all4u_views_registered=True
    if not auto_backup.is_running():auto_backup.start()
    if not cleanup_archive.is_running():cleanup_archive.start()

@bot.event
async def on_message(message):
    if message.guild and not message.author.bot:
        guild=message.guild
        conn.execute('INSERT OR REPLACE INTO messages VALUES(?,?,?,?,?,?,?)',(guild.id,message.channel.id,message.id,message.author.id,str(message.author),message.content[:4000],message.created_at.isoformat()))
        conn.commit()
        exempt=message.author.guild_permissions.manage_messages or trusted(guild.id,message.author.id)
        if (enabled(guild.id,'antilink') or enabled(guild.id,'raidmode')) and not exempt and LINK_RE.search(message.content):
            try:
                await message.delete()
                await notify(guild,f'🔗 Anti-Link: đã xóa liên kết từ {message.author}.')
            except (discord.Forbidden,discord.HTTPException):pass
            return
        if (enabled(guild.id,'antispam') or enabled(guild.id,'raidmode')) and not exempt:
            now=asyncio.get_running_loop().time(); q=spam[(guild.id,message.author.id)]
            q.append(now)
            window=5 if enabled(guild.id,"raidmode") else 8
            threshold=4 if enabled(guild.id,"raidmode") else 7
            while q and now-q[0]>window:q.popleft()
            if len(q)>=threshold:
                try:
                    await message.delete()
                    await message.author.timeout(timedelta(minutes=5),reason='All4u anti-spam')
                    await notify(guild,f'🛡️ Anti-Spam: đã tạm hạn chế {message.author} trong 5 phút.')
                except (discord.Forbidden,discord.HTTPException):pass
                q.clear()
                return
    if message.guild and not message.author.bot and message.content.strip().lower()=='tabo':
        await message.channel.send(f'<@{OWNER_ID}>',allowed_mentions=discord.AllowedMentions(users=True,roles=False,everyone=False))
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    if not (enabled(member.guild.id,'antiraid') or enabled(member.guild.id,'raidmode')):return
    now=asyncio.get_running_loop().time();q=raid[member.guild.id];q.append(now)
    while q and now-q[0]>15:q.popleft()
    if len(q)>=(4 if enabled(member.guild.id,"raidmode") else 8):
        await notify(member.guild,'⚠️ Anti-Raid: phát hiện nhiều thành viên tham gia trong 15 giây. Hãy kiểm tra quyền mời và bật xác minh.')
        q.clear()

@bot.event
async def on_guild_channel_delete(channel):
    if enabled(channel.guild.id,'antinuke') or enabled(channel.guild.id,'raidmode'):
        await notify(channel.guild,f'⚠️ Anti-Nuke: kênh `{channel.name}` vừa bị xóa. Dùng `?backup_list` và `?restore_preview` để kiểm tra bản sao lưu.')

@bot.event
async def on_guild_role_delete(role):
    if enabled(role.guild.id,'antinuke') or enabled(role.guild.id,'raidmode'):
        await notify(role.guild,f'⚠️ Anti-Nuke: role `{role.name}` vừa bị xóa.')

@tasks.loop(minutes=BACKUP_MINUTES)
async def auto_backup():
    for g in bot.guilds:
        try:await make_backup(g)
        except Exception:log.exception('backup failed %s',g.id)

@auto_backup.before_loop
async def before_backup():await bot.wait_until_ready()

@tasks.loop(hours=24)
async def cleanup_archive():
    cutoff=(datetime.now(timezone.utc)-timedelta(days=ARCHIVE_DAYS)).isoformat()
    conn.execute('DELETE FROM messages WHERE created < ?',(cutoff,));conn.commit()

@cleanup_archive.before_loop
async def before_cleanup():await bot.wait_until_ready()

@bot.command(name='help')
async def help_cmd(ctx):
    embed = discord.Embed(
        title='𝙃𝙤𝙖𝙣𝙜 𝙏𝙪 𝙈𝙪𝙖 𝘿𝙤𝙣𝙜',
        description='**ALL COMMANDS** • Prefix: `?`\nDanh sách lệnh quản lý và bảo mật.',
        color=discord.Color.from_rgb(139, 128, 218)
    )
    sections = [
        ('🛡️ SECURITY', [
            ('?menu', 'Bảng điều khiển Security'),
            ('?antinuke on/off', 'Bật/tắt Anti-Nuke'),
            ('?antiraid on/off', 'Bật/tắt Anti-Raid'),
            ('?antispam on/off', 'Bật/tắt Anti-Spam'),
            ('?antilink on/off', 'Bật/tắt Anti-Link'),
            ('?raidmode on/off', 'Bật/tắt Raid Mode'),
            ('?antibot on/off', 'Tự động kick bot phá hoại'),
            ('?antibot_status', 'Trạng thái Anti-Rogue Bot'),
            ('?antibot_whitelist add/remove/list', 'Danh sách bot tin cậy')]),
        ('💾 BACKUP & RECOVERY', [
            ('?backup', 'Mở bảng Backup & Recovery'),
            ('?backup_create', 'Tạo bản sao lưu'),
            ('?backup_list', 'Danh sách bản sao lưu'),
            ('?backup_export [id]', 'Xuất bản sao lưu'),
            ('?restore_preview [id]', 'Xem trước khôi phục'),
            ('?restore_missing [id]', 'Tạo lại role/kênh bị thiếu'),
            ('?message_restore [1-20]', 'Trả lời bản lưu tin nhắn ngay trong kênh chat'),
            ('?recovery_full [id]', 'Khôi phục mục bị thiếu từ backup'),
            ('?recovery_status', 'Trạng thái phục hồi'),
            ('?recovery_messages [1-20]', 'Đăng lại tin nhắn đã lưu'),
            ('?recovery_cancel', 'Dừng phục hồi')]),
        ('⚙️ MANAGEMENT', [
            ('?whitelist add @user', 'Thêm người tin cậy'),
            ('?whitelist remove @user', 'Xóa người tin cậy'),
            ('?whitelist list', 'Xem whitelist'),
            ('?setlog #channel', 'Thiết lập kênh log'),
            ('?status', 'Trạng thái bảo vệ')]),
        ('🔨 MODERATION', [
            ('?warn @user [lý do]', '⚠️ Cảnh cáo thành viên'),
            ('?warning @user', '📋 Lịch sử cảnh cáo'),
            ('?mute @user 10m [lý do]', '🔇 Timeout thành viên'),
            ('?unmute @user', '🔊 Gỡ timeout'),
            ('?ban @user [lý do]', '🔨 Cấm thành viên'),
            ('?unban user_id', '🔓 Gỡ cấm'),
            ('?kick @user [lý do]', '👢 Đuổi thành viên'),
            ('?clear 10', '🧹 Xóa tin nhắn')]),
        ('📋 GENERAL', [
            ('?help', 'Hiển thị tất cả lệnh'),
            ('?ping', 'Kiểm tra độ trễ')])
    ]
    for title, commands_list in sections:
        embed.add_field(name=title, value='\n'.join(f'`{cmd}` — {desc}' for cmd, desc in commands_list), inline=False)
    embed.set_image(url=HELP_GIF or 'attachment://help.gif')
    embed.set_footer(text='Hoang Tu Mua Dong • All4u Security System')
    await ctx.send(embed=embed,file=gif_attachment('help') if not HELP_GIF else None)

@bot.command()
async def ping(ctx):await ctx.send(f'Pong! {round(bot.latency*1000)}ms')

@bot.command()
async def status(ctx):
    g=ctx.guild
    if not g:return
    await ctx.send(' | '.join(f'{k}: {setting(g.id,k)}' for k in SECURITY_KEYS))

class BackupPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="💾 Backup", style=discord.ButtonStyle.primary)
    async def backup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("💾 Sao lưu: `?backup_create`, `?backup_list`, `?backup_export [id]`, `?restore_preview [id]`, `?restore_missing [id]`.")

    @discord.ui.button(label="♻️ Recovery", style=discord.ButtonStyle.secondary)
    async def recovery_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("♻️ Phục hồi: `?recovery_full [id]`, `?recovery_status`, `?recovery_messages [1-20]`, `?recovery_cancel`.")

    @discord.ui.button(label="🤖 Anti-Bot", style=discord.ButtonStyle.secondary)
    async def antibot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🤖 Anti-Rogue: `?antibot on/off`, `?antibot_status`, `?antibot_whitelist add/remove/list`.")

@bot.command(name='backup')
@commands.guild_only()
async def backup_panel(ctx):
    embed=discord.Embed(title="💾 𝙃𝙤𝙖𝙣𝙜 𝙏𝙪 𝙈𝙪𝙖 𝘿𝙤𝙣𝙜", description="**BACKUP & RECOVERY CONTROL PANEL**",color=discord.Color.from_rgb(130,149,219))
    embed.add_field(name="💾 BACKUP SYSTEM",value="`?backup_create` — Tạo bản sao lưu\n`?backup_list` — Danh sách sao lưu\n`?backup_export [id]` — Xuất dữ liệu\n`?restore_preview [id]` — Xem trước\n`?restore_missing [id]` — Phục hồi mục thiếu",inline=False)
    embed.add_field(name="♻️ SERVER RECOVERY",value="`?recovery_full [id]` — Phục hồi server\n`?recovery_status` — Tiến độ\n`?recovery_messages [1-20]` — Phục hồi tin nhắn\n`?recovery_cancel` — Dừng phục hồi",inline=False)
    embed.add_field(name="🤖 ANTI-ROGUE BOT",value="`?antibot on/off` — Bật/tắt\n`?antibot_status` — Trạng thái\n`?antibot_whitelist` — Danh sách tin cậy",inline=False)
    embed.set_image(url="attachment://backup.gif")
    embed.set_footer(text="Hoang Tu Mua Dong • Backup & Recovery System")
    await ctx.send(embed=embed,view=BackupPanelView(),file=gif_attachment('backup'))

@bot.command(name='backup_create')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def backup_create(ctx):
    await make_backup(ctx.guild)
    await ctx.send('✅ Đã sao lưu cấu trúc server (role, category, text/voice channel).')

@bot.command(name='backup_list')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def backup_list(ctx):
    rows=conn.execute('SELECT id,created FROM backups WHERE guild=? ORDER BY id DESC LIMIT 10',(ctx.guild.id,)).fetchall()
    await ctx.send('\n'.join(f'`{i}` — {dt[:19]} UTC' for i,dt in rows) if rows else 'Chưa có bản sao lưu.')

def get_backup(g,ident):
    if ident is None:
        row=conn.execute('SELECT data FROM backups WHERE guild=? ORDER BY id DESC LIMIT 1',(g,)).fetchone()
    else:row=conn.execute('SELECT data FROM backups WHERE guild=? AND id=?',(g,ident)).fetchone()
    return json.loads(row[0]) if row else None

@bot.command(name='backup_export')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def backup_export(ctx,ident:int=None):
    data=get_backup(ctx.guild.id,ident)
    if not data:return await ctx.send('Không tìm thấy backup.')
    # Backup data may include private channel names and role structure.
    # Publish the file only where ordinary members cannot read it.
    if ctx.channel.permissions_for(ctx.guild.default_role).read_messages:
        return await ctx.send('🔒 File backup chứa cấu trúc máy chủ. Hãy chạy lệnh trong kênh quản trị riêng để xuất công khai trong kênh đó.')
    b=io.BytesIO(json.dumps(data,ensure_ascii=False,indent=2).encode())
    await ctx.send('💾 Bản sao lưu:',file=discord.File(b,filename='all4u_backup.json'))

@bot.command(name='restore_preview')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def restore_preview(ctx,ident:int=None):
    data=get_backup(ctx.guild.id,ident)
    if not data:return await ctx.send('Không tìm thấy backup.')
    roles={r.name for r in ctx.guild.roles};categories={c.name for c in ctx.guild.categories};channels={(c.name,'text' if isinstance(c,discord.TextChannel) else 'voice') for c in ctx.guild.channels}
    missing_roles=sum(r['name'] not in roles for r in data['roles']);missing_cats=sum(c['name'] not in categories for c in data['categories']);missing_channels=sum((c['name'],c['type']) not in channels for c in data['channels'] if c['type']!='other')
    await ctx.send(f'Xem trước: thiếu **{missing_roles} roles**, **{missing_cats} categories**, **{missing_channels} channels**. Dùng `?restore_missing {ident or ""}` để tạo phần thiếu. Không khôi phục được lịch sử Discord hoặc quyền ghi đè phức tạp.')

@bot.command(name='restore_missing')
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def restore_missing(ctx,ident:int=None):
    data=get_backup(ctx.guild.id,ident)
    if not data:return await ctx.send('Không tìm thấy backup.')
    g=ctx.guild;created=0
    for r in data['roles']:
        if discord.utils.get(g.roles,name=r['name']):continue
        try:
            await g.create_role(name=r['name'],color=discord.Color(r['color']),permissions=discord.Permissions(r['permissions']),hoist=r['hoist'],mentionable=r['mentionable'],reason='All4u restore');created+=1
        except (discord.Forbidden,discord.HTTPException):pass
    for c in data['categories']:
        if discord.utils.get(g.categories,name=c['name']):continue
        try:await g.create_category(c['name'],reason='All4u restore');created+=1
        except (discord.Forbidden,discord.HTTPException):pass
    for c in data['channels']:
        if c['type'] not in ('text','voice'):continue
        existing=any(x.name==c['name'] and ((c['type']=='text' and isinstance(x,discord.TextChannel)) or (c['type']=='voice' and isinstance(x,discord.VoiceChannel))) for x in g.channels)
        if existing:continue
        category=discord.utils.get(g.categories,name=c['category']) if c['category'] else None
        try:
            if c['type']=='text':await g.create_text_channel(c['name'],category=category,topic=c.get('topic'),nsfw=c.get('nsfw',False),reason='All4u restore')
            else:await g.create_voice_channel(c['name'],category=category,reason='All4u restore')
            created+=1
        except (discord.Forbidden,discord.HTTPException):pass
    await ctx.send(f'✅ Đã tạo {created} mục bị thiếu. Các mục hiện có được giữ nguyên.')

@bot.command(name='message_restore')
@commands.guild_only()
@commands.has_guild_permissions(manage_messages=True)
@commands.bot_has_guild_permissions(send_messages=True, embed_links=True)
async def message_restore(ctx, limit: int = 10):
    """Reply in the current public channel with archived messages from that channel."""
    limit = max(1, min(limit, 20))
    # Fetch extra records because commands and empty messages are excluded.
    rows = conn.execute(
        'SELECT message,author,author_name,content,created FROM messages '
        'WHERE guild=? AND channel=? AND message != ? '
        'ORDER BY created DESC LIMIT ?',
        (ctx.guild.id, ctx.channel.id, ctx.message.id, min(200, limit * 10))
    ).fetchall()
    selected = [(mid, author_id, author, content, created) for mid, author_id, author, content, created in rows
                if content and content.strip() and not content.lstrip().startswith('?')][:limit]
    if not selected:
        return await ctx.reply('📭 Không có tin nhắn phù hợp trong bản lưu của kênh này.', mention_author=False)
    await ctx.reply(
        f'📜 **Đang phục hồi {len(selected)} tin nhắn đã lưu** ngay tại kênh này. '
        'Đây là bản sao nội dung, không phải tin nhắn Discord gốc.',
        mention_author=False, allowed_mentions=discord.AllowedMentions.none()
    )
    success = 0
    for mid, author_id, author, content, created in reversed(selected):
        embed = discord.Embed(
            title='📜 Restored Message',
            description=discord.utils.escape_mentions(content[:3900]),
            color=discord.Color.blurple()
        )
        embed.add_field(name='👤 Người gửi ban đầu', value=discord.utils.escape_markdown(author[:200]), inline=False)
        embed.set_footer(text=f'🕒 {created[:19].replace("T", " ")} UTC • Bản lưu ID {mid}')
        try:
            await ctx.message.reply(content=f'<@{author_id}>', embed=embed, mention_author=False,
                                    allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=author_id)], roles=False, everyone=False))
            success += 1
        except (discord.Forbidden, discord.HTTPException):
            break
    if success != len(selected):
        await ctx.send(f'⚠️ Đã đăng {success}/{len(selected)} bản lưu. Kiểm tra quyền gửi tin nhắn/Embed.',
                       allowed_mentions=discord.AllowedMentions.none())

@bot.command(name='antinuke')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def antinuke(ctx,value:str):await toggle(ctx,'antinuke',value)
@bot.command(name='antiraid')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def antiraid(ctx,value:str):await toggle(ctx,'antiraid',value)
@bot.command(name='antispam')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def antispam(ctx,value:str):await toggle(ctx,'antispam',value)
@bot.command(name='antilink')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def antilink(ctx,value:str):await toggle(ctx,'antilink',value)
@bot.command(name='raidmode')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def raidmode(ctx,value:str):await toggle(ctx,'raidmode',value)

async def toggle(ctx,key,value):
    if value not in ('on','off'):return await ctx.send(f'Dùng `?{key} on` hoặc `?{key} off`.')
    save_setting(ctx.guild.id,key,value)
    await ctx.send(f'✅ {key}: {value}')

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def whitelist(ctx,action:str,member:discord.Member=None):
    if action=='list':
        ids=conn.execute('SELECT user FROM trusted WHERE guild=?',(ctx.guild.id,)).fetchall()
        return await ctx.send('Trusted IDs: '+(', '.join(str(x[0]) for x in ids) if ids else 'trống'))
    if action not in ('add','remove') or member is None:return await ctx.send('Dùng `?whitelist add/remove @user` hoặc `?whitelist list`.')
    if action=='add':conn.execute('INSERT OR IGNORE INTO trusted VALUES(?,?)',(ctx.guild.id,member.id))
    else:conn.execute('DELETE FROM trusted WHERE guild=? AND user=?',(ctx.guild.id,member.id))
    conn.commit();await ctx.send('✅ Đã cập nhật whitelist.')

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def setlog(ctx,channel:discord.TextChannel):
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID=channel.id
    await ctx.send(f'Log channel tạm thời: {channel.mention}. Để lưu qua restart, đặt LOG_CHANNEL_ID trong .env.')


# Moderation: all commands are restricted to appropriate Discord permissions.
def can_target(ctx, member):
    if member.id == ctx.guild.owner_id or member.id == ctx.author.id or member.id == bot.user.id:
        return False
    if ctx.author.id != ctx.guild.owner_id and member.top_role >= ctx.author.top_role:
        return False
    if member.top_role >= ctx.guild.me.top_role:
        return False
    return True

async def mod_result(ctx, emoji, title, member, reason=None, detail=None):
    e=discord.Embed(title=f'{emoji} {title}', color=discord.Color.blurple())
    e.add_field(name='👤 Thành viên',value=f'{member.mention} (`{member.id}`)',inline=False)
    e.add_field(name='🛡️ Moderator',value=ctx.author.mention,inline=False)
    if reason:e.add_field(name='📝 Lý do',value=reason[:1000],inline=False)
    if detail:e.add_field(name='📋 Chi tiết',value=detail,inline=False)
    e.set_footer(text='𝙃𝙤𝙖𝙣𝙜 𝙏𝙪 𝙈𝙪𝙖 𝘿𝙤𝙣𝙜')
    await ctx.send(embed=e,allowed_mentions=discord.AllowedMentions.none())

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(moderate_members=True)
async def warn(ctx, member:discord.Member, *, reason:str='Không có lý do'):
    if not can_target(ctx,member):return await ctx.send('⛔ Không thể cảnh cáo thành viên này.')
    conn.execute('INSERT INTO warnings(guild,user,moderator,reason,created) VALUES(?,?,?,?,?)',
        (ctx.guild.id,member.id,ctx.author.id,reason[:1000],datetime.now(timezone.utc).isoformat()))
    conn.commit()
    total=conn.execute('SELECT COUNT(*) FROM warnings WHERE guild=? AND user=?',(ctx.guild.id,member.id)).fetchone()[0]
    await mod_result(ctx,'⚠️','MEMBER WARNED',member,reason,f'Tổng cảnh cáo: {total}')

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(moderate_members=True)
async def warning(ctx, member:discord.Member):
    rows=conn.execute('SELECT moderator,reason,created FROM warnings WHERE guild=? AND user=? ORDER BY id DESC LIMIT 10',(ctx.guild.id,member.id)).fetchall()
    total=conn.execute('SELECT COUNT(*) FROM warnings WHERE guild=? AND user=?',(ctx.guild.id,member.id)).fetchone()[0]
    e=discord.Embed(title='📋 WARNING HISTORY',description=f'{member.mention} • Tổng cảnh cáo: **{total}**',color=discord.Color.gold())
    e.add_field(name='Cảnh cáo gần nhất',value='\n'.join(f'{i}. {reason[:140]} — <@{mod}>' for i,(mod,reason,created) in enumerate(rows,1)) if rows else 'Chưa có cảnh cáo.',inline=False)
    await ctx.send(embed=e,allowed_mentions=discord.AllowedMentions.none())

def parse_duration(value):
    match=re.fullmatch(r'(\d+)([mhd])',value.lower())
    if not match:return None
    amount=int(match.group(1)); unit=match.group(2)
    duration=timedelta(minutes=amount) if unit=='m' else timedelta(hours=amount) if unit=='h' else timedelta(days=amount)
    return duration if timedelta(seconds=1)<=duration<=timedelta(days=28) else None

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(moderate_members=True)
@commands.bot_has_guild_permissions(moderate_members=True)
async def mute(ctx,member:discord.Member,duration:str='10m',*,reason:str='Không có lý do'):
    delta=parse_duration(duration)
    if delta is None:return await ctx.send('⚠️ Thời gian hợp lệ: 10m, 2h, 1d (tối đa 28d).')
    if not can_target(ctx,member) or member.guild_permissions.administrator:return await ctx.send('⛔ Không thể timeout thành viên này.')
    await member.timeout(delta,reason=f'{ctx.author}: {reason}'[:512])
    await mod_result(ctx,'🔇','MEMBER MUTED',member,reason,f'Thời gian: {duration}')

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(moderate_members=True)
@commands.bot_has_guild_permissions(moderate_members=True)
async def unmute(ctx,member:discord.Member):
    if not can_target(ctx,member):return await ctx.send('⛔ Không thể gỡ timeout cho thành viên này.')
    await member.timeout(None,reason=f'Unmute by {ctx.author}')
    await mod_result(ctx,'🔊','MEMBER UNMUTED',member)

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(ban_members=True)
@commands.bot_has_guild_permissions(ban_members=True)
async def ban(ctx,member:discord.Member,*,reason:str='Không có lý do'):
    if not can_target(ctx,member):return await ctx.send('⛔ Không thể ban thành viên này.')
    await ctx.guild.ban(member,reason=f'{ctx.author}: {reason}'[:512],delete_message_seconds=0)
    await mod_result(ctx,'🔨','MEMBER BANNED',member,reason)

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(ban_members=True)
@commands.bot_has_guild_permissions(ban_members=True)
async def unban(ctx,user_id:int):
    user=await bot.fetch_user(user_id)
    await ctx.guild.unban(user,reason=f'Unban by {ctx.author}')
    await ctx.send(f'🔓 Đã gỡ ban: `{user_id}`')

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(kick_members=True)
@commands.bot_has_guild_permissions(kick_members=True)
async def kick(ctx,member:discord.Member,*,reason:str='Không có lý do'):
    if not can_target(ctx,member):return await ctx.send('⛔ Không thể kick thành viên này.')
    await ctx.guild.kick(member,reason=f'{ctx.author}: {reason}'[:512])
    await mod_result(ctx,'👢','MEMBER KICKED',member,reason)

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(manage_messages=True)
@commands.bot_has_guild_permissions(manage_messages=True)
async def clear(ctx,amount:int):
    if not 1<=amount<=100:return await ctx.send('⚠️ Nhập số từ 1 đến 100.')
    deleted=await ctx.channel.purge(limit=amount+1)
    await ctx.send(f'🧹 Đã xóa {max(0,len(deleted)-1)} tin nhắn.')


# Only confirmed audit-log actions count; never punish a human or trusted bot.
rogue_actions=defaultdict(deque)
ROGUE_WINDOW=20
ROGUE_THRESHOLD=3

def bot_allowed(guild_id, bot_id):
    return bool(conn.execute('SELECT 1 FROM antibot_allow WHERE guild=? AND bot_id=?',(guild_id,bot_id)).fetchone())

@bot.event
async def on_audit_log_entry_create(entry):
    g=entry.guild
    if not (enabled(g.id,'antibot') or enabled(g.id,'raidmode')):return
    monitored={discord.AuditLogAction.channel_delete,discord.AuditLogAction.role_delete,
               discord.AuditLogAction.channel_update,discord.AuditLogAction.role_update}
    if entry.action not in monitored:return
    actor=entry.user
    if not actor or not actor.bot or actor.id==bot.user.id or bot_allowed(g.id,actor.id):return
    member=g.get_member(actor.id)
    if member is None:
        try:member=await g.fetch_member(actor.id)
        except (discord.NotFound,discord.Forbidden,discord.HTTPException):return
    if member.id==g.owner_id or not g.me or member.top_role>=g.me.top_role:return
    now=asyncio.get_running_loop().time()
    q=rogue_actions[(g.id,member.id)]
    q.append(now)
    while q and now-q[0]>ROGUE_WINDOW:q.popleft()
    if len(q)<ROGUE_THRESHOLD:return
    q.clear()
    try:
        await member.kick(reason='All4u: 3 confirmed destructive audit-log actions in 20 seconds')
        await notify(g,f'🤖 Anti-Rogue Bot: đã kick bot `{member}` ({member.id}) sau 3 hành động audit log bất thường trong 20 giây.')
    except (discord.Forbidden,discord.HTTPException):
        await notify(g,f'⚠️ Anti-Rogue Bot: phát hiện bot `{member}` ({member.id}) nhưng không đủ quyền kick.')

recovery_tasks={}
recovery_cancel_flags={}

def recovery_job(g,status,details=''):
    conn.execute('INSERT OR REPLACE INTO recovery_jobs VALUES(?,?,?,?)',(g,status,datetime.now(timezone.utc).isoformat(),details));conn.commit()

@bot.command(name='antibot')
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def antibot(ctx,value:str):
    await toggle(ctx,'antibot',value)

@bot.command(name='antibot_status')
@commands.guild_only()
async def antibot_status(ctx):
    count=conn.execute('SELECT COUNT(*) FROM antibot_allow WHERE guild=?',(ctx.guild.id,)).fetchone()[0]
    await ctx.send(f'🤖 Anti-Rogue Bot: **{setting(ctx.guild.id,"antibot").upper()}** • {count} bot tin cậy • ngưỡng 3 hành động/20 giây.')

@bot.group(name='antibot_whitelist',invoke_without_command=True)
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def antibot_whitelist(ctx):
    await ctx.send('📋 Dùng `?antibot_whitelist add <bot_id>`, `remove <bot_id>`, hoặc `list`.')

@antibot_whitelist.command(name='add')
async def antibot_whitelist_add(ctx,bot_id:int):
    member=ctx.guild.get_member(bot_id)
    if not member:
        try:member=await ctx.guild.fetch_member(bot_id)
        except (discord.NotFound,discord.HTTPException):return await ctx.send('Không tìm thấy bot trong server.')
    if not member.bot:return await ctx.send('ID này không phải bot.')
    conn.execute('INSERT OR IGNORE INTO antibot_allow VALUES(?,?)',(ctx.guild.id,bot_id));conn.commit()
    await ctx.send(f'✅ Đã tin cậy bot `{bot_id}`.')

@antibot_whitelist.command(name='remove')
async def antibot_whitelist_remove(ctx,bot_id:int):
    conn.execute('DELETE FROM antibot_allow WHERE guild=? AND bot_id=?',(ctx.guild.id,bot_id));conn.commit()
    await ctx.send(f'✅ Đã bỏ tin cậy bot `{bot_id}`.')

@antibot_whitelist.command(name='list')
async def antibot_whitelist_list(ctx):
    ids=[r[0] for r in conn.execute('SELECT bot_id FROM antibot_allow WHERE guild=?',(ctx.guild.id,))]
    await ctx.send('📋 Bot tin cậy: '+(', '.join(map(str,ids)) if ids else 'Chưa có'))

async def run_full_recovery(ctx,backup_id):
    g=ctx.guild
    data=get_backup(g.id,backup_id)
    if not data:return await ctx.send('❌ Không tìm thấy bản sao lưu.')
    recovery_cancel_flags[g.id]=False
    recovery_job(g.id,'running','Starting non-destructive recovery')
    created=0;errors=0
    try:
        for r in sorted(data.get('roles',[]),key=lambda x:x.get('position',0)):
            if recovery_cancel_flags.get(g.id):break
            if discord.utils.get(g.roles,name=r['name']):continue
            try:
                await g.create_role(name=r['name'],color=discord.Color(r['color']),permissions=discord.Permissions(r['permissions']),hoist=r['hoist'],mentionable=r['mentionable'],reason='All4u full recovery');created+=1
            except (discord.Forbidden,discord.HTTPException):errors+=1
        for c in data.get('categories',[]):
            if recovery_cancel_flags.get(g.id):break
            if discord.utils.get(g.categories,name=c['name']):continue
            try:await g.create_category(c['name'],reason='All4u full recovery');created+=1
            except (discord.Forbidden,discord.HTTPException):errors+=1
        for c in data.get('channels',[]):
            if recovery_cancel_flags.get(g.id):break
            if c['type'] not in ('text','voice'):continue
            if any(x.name==c['name'] and ((c['type']=='text' and isinstance(x,discord.TextChannel)) or (c['type']=='voice' and isinstance(x,discord.VoiceChannel))) for x in g.channels):continue
            category=discord.utils.get(g.categories,name=c['category']) if c.get('category') else None
            try:
                if c['type']=='text':await g.create_text_channel(c['name'],category=category,topic=c.get('topic'),nsfw=c.get('nsfw',False),reason='All4u full recovery')
                else:await g.create_voice_channel(c['name'],category=category,reason='All4u full recovery')
                created+=1
            except (discord.Forbidden,discord.HTTPException):errors+=1
        state='cancelled' if recovery_cancel_flags.get(g.id) else 'completed'
        recovery_job(g.id,state,f'created={created}; errors={errors}')
        await ctx.send(f'♻️ Recovery {state}: đã tạo {created} mục, lỗi quyền/API: {errors}. Không xóa mục hiện có.')
    except Exception as e:
        recovery_job(g.id,'failed',str(e)[:300]);log.exception('recovery failed')
        await ctx.send('⚠️ Recovery lỗi; xem Deploy Logs.')
    finally:recovery_tasks.pop(g.id,None)

@bot.command(name='recovery_full')
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def recovery_full(ctx,backup_id:int=None):
    if ctx.guild.id in recovery_tasks:return await ctx.send('⏳ Recovery đang chạy.')
    if not get_backup(ctx.guild.id,backup_id):return await ctx.send('❌ Chưa có bản sao lưu.')
    await ctx.send('♻️ Bắt đầu khôi phục các role, category và kênh bị thiếu từ backup. Không xóa dữ liệu hiện có.')
    recovery_tasks[ctx.guild.id]=asyncio.create_task(run_full_recovery(ctx,backup_id))

@bot.command(name='recovery_status')
@commands.guild_only()
async def recovery_status(ctx):
    row=conn.execute('SELECT status,created,details FROM recovery_jobs WHERE guild=?',(ctx.guild.id,)).fetchone()
    await ctx.send('📊 '+(f'**{row[0]}** • {row[1]} • {row[2]}' if row else 'Chưa có recovery.'))

@bot.command(name='recovery_cancel')
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def recovery_cancel(ctx):
    if ctx.guild.id not in recovery_tasks:return await ctx.send('Không có recovery đang chạy.')
    recovery_cancel_flags[ctx.guild.id]=True
    await ctx.send('🛑 Đã yêu cầu dừng; bot sẽ dừng sau thao tác API hiện tại.')

@bot.command(name='recovery_messages')
@commands.guild_only()
@commands.has_guild_permissions(manage_messages=True)
async def recovery_messages(ctx,limit:int=10):
    # Reuse the existing message restore implementation, including its permission checks.
    await ctx.invoke(message_restore,limit=max(1,min(limit,20)))

@bot.event
async def on_command_error(ctx,error):
    if isinstance(error,commands.CommandNotFound):return
    if isinstance(error,commands.MissingPermissions):return await ctx.send('⛔ Bạn không có quyền sử dụng lệnh này.')
    if isinstance(error,(commands.MissingRequiredArgument,commands.BadArgument)):return await ctx.send('⚠️ Sai tham số. Xem `?help`.')
    log.error('Command error: %r',error)
    await ctx.send('⚠️ Lệnh gặp lỗi. Kiểm tra log bot.')

async def health(request):return web.json_response({'online':bot.is_ready(),'guilds':len(bot.guilds)})
async def dashboard(request):
    if not DASHBOARD_KEY or request.headers.get('Authorization')!=f'Bearer {DASHBOARD_KEY}':
        return web.json_response({'error':'unauthorized'},status=401)
    return web.json_response({'bot':str(bot.user),'guilds':[{'id':g.id,'name':g.name,'members':g.member_count} for g in bot.guilds]})

async def main():
    if not TOKEN:raise RuntimeError('Set DISCORD_TOKEN in config.py')
    app=web.Application();app.router.add_get('/health',health);app.router.add_get('/api/status',dashboard)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'0.0.0.0',PORT).start()
    try:await bot.start(TOKEN)
    finally:await runner.cleanup();conn.close()

if __name__=='__main__':asyncio.run(main())
