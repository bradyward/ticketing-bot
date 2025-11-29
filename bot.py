import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from datetime import datetime, timedelta, time
import asyncio

# Configure bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== CONFIGURABLE VARIABLES =====
LEAD_BUTTON_TIMEOUT_MINUTES = 0
SAMPLE_LEADS = [
    {"name": "John Smith", "phone": "555-0001", "email": "john@example.com"},
    {"name": "Jane Doe", "phone": "555-0002", "email": "jane@example.com"},
    {"name": "Bob Johnson", "phone": "555-0003", "email": "bob@example.com"},
]
# ===================================

# Store ticket data and lead tracking
ticket_data = {}  # {user_id: {name, hours, audio_link}}
lead_cooldowns = {}  # {user_id: last_press_time}
daily_lead_counts = {}  # {user_id: count}
lead_channel_messages = {}  # {message_id: (user_id, channel_id)}

# Channel IDs (configure these)
ENTRY_CHANNEL_ID = None
TICKET_CHANNEL_ID = None
LEADS_CHANNEL_ID = None
DAILY_REPORT_CHANNEL_ID = None
TICKETS_CATEGORY_ID = None

# Role names
STAFF_ROLE = "ticket_staff"
CALLER_ROLE = "caller"
VIEWER_ROLE = "*"

@bot.event
async def on_ready():
    print(f"✓ Bot logged in as {bot.user}")
    await bot.tree.sync()
    daily_report.start()

@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction to close lead tickets"""
    if user.bot:
        return
    
    if reaction.emoji != "❌":
        return
    
    message_id = reaction.message.id
    if message_id not in lead_channel_messages:
        return
    
    lead_creator_id, channel_id = lead_channel_messages[message_id]
    
    # Check if the person closing is the one who created it
    if user.id != lead_creator_id:
        await reaction.message.remove_reaction("❌", user)
        return
    
    # Close the ticket
    try:
        await reaction.message.delete()
        del lead_channel_messages[message_id]
        
        # Delete the channel
        lead_channel = bot.get_channel(channel_id)
        if lead_channel:
            # Send report to daily_report when channel cleared
            daily_report_channel = bot.get_channel(DAILY_REPORT_CHANNEL_ID)
            if daily_report_channel:
                embed = discord.Embed(
                    title="Lead Ticket Channel Cleared",
                    description=f"{user.mention} cleared their lead ticket channel",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                await daily_report_channel.send(embed=embed)
            
            await lead_channel.delete()
    except Exception as e:
        print(f"Error closing ticket: {e}")

@bot.command()
async def setup(ctx):
    """Setup command to create all roles and channels"""
    viewer_role = discord.utils.get(ctx.guild.roles, name=VIEWER_ROLE)
    if not viewer_role or viewer_role not in ctx.author.roles:
        await ctx.send("Only users with the * role can run this command.")
        return
    
    # Ask for password confirmation
    await ctx.send("Enter the password to confirm setup:")
    try:
        msg = await bot.wait_for('message', timeout=30, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
        if msg.content != "confirmsetup":
            await ctx.send("❌ Incorrect password.")
            return
    except asyncio.TimeoutError:
        await ctx.send("⏱ Setup confirmation timed out.")
        return
    
    global ENTRY_CHANNEL_ID, LEADS_CHANNEL_ID, DAILY_REPORT_CHANNEL_ID, TICKETS_CATEGORY_ID
    
    guild = ctx.guild
    await ctx.send("⏳ Creating roles and channels...")
    
    try:
        # Create or overwrite roles
        ticket_staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE)
        if ticket_staff_role:
            await ticket_staff_role.delete()
        ticket_staff_role = await guild.create_role(name=STAFF_ROLE, color=discord.Color.red())
        print(f"✓ Created role: {STAFF_ROLE}")
        
        caller_role = discord.utils.get(guild.roles, name=CALLER_ROLE)
        if caller_role:
            await caller_role.delete()
        caller_role = await guild.create_role(name=CALLER_ROLE, color=discord.Color.green())
        print(f"✓ Created role: {CALLER_ROLE}")
        
        # Note: * role is an admin role and should not be created or modified by the bot
        
        # Create or overwrite tickets category
        tickets_category = discord.utils.get(guild.categories, name="tickets")
        if tickets_category:
            await tickets_category.delete()
        tickets_category = await guild.create_category("tickets")
        TICKETS_CATEGORY_ID = tickets_category.id
        print(f"✓ Created category: tickets")
        
        # Create or overwrite entry channel
        entry_channel = discord.utils.get(guild.channels, name="entry")
        if entry_channel:
            await entry_channel.delete()
        entry_channel = await guild.create_text_channel(
            "entry",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=True)
            }
        )
        ENTRY_CHANNEL_ID = entry_channel.id
        print(f"✓ Created channel: entry")
        
        # Create or overwrite leads channel
        leads_channel = discord.utils.get(guild.channels, name="leads")
        if leads_channel:
            await leads_channel.delete()
        leads_channel = await guild.create_text_channel(
            "leads",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                caller_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                ticket_staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )
        LEADS_CHANNEL_ID = leads_channel.id
        print(f"✓ Created channel: leads")
        
        # Create or overwrite daily_report channel
        daily_report_channel = discord.utils.get(guild.channels, name="daily_report")
        if daily_report_channel:
            await daily_report_channel.delete()
        daily_report_channel = await guild.create_text_channel(
            "daily_report",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                ticket_staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )
        DAILY_REPORT_CHANNEL_ID = daily_report_channel.id
        print(f"✓ Created channel: daily_report")
        
        # Initialize entry and leads
        await init_entry_internal(entry_channel)
        await init_leads_internal(leads_channel)
        
        await ctx.send(f"✓ Setup complete!\nRoles created: {STAFF_ROLE}, {CALLER_ROLE}\nChannels created: entry, leads, daily_report\nCategory created: tickets")
        
    except Exception as e:
        await ctx.send(f"⚠ Error during setup: {e}")
        print(f"Setup error: {e}")

@bot.command()
async def init_entry(ctx):
    """Initialize the entry channel with the ticket button"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Only administrators can run this command.")
        return
    
    if ENTRY_CHANNEL_ID is None:
        await ctx.send("Run !setup first.")
        return
    
    channel = bot.get_channel(ENTRY_CHANNEL_ID)
    await init_entry_internal(channel)
    await ctx.send("✓ Entry message sent.")

async def init_entry_internal(channel):
    embed = discord.Embed(
        title="Create a Support Ticket",
        description="Click the button below to create a support ticket.",
        color=discord.Color.blue()
    )
    await channel.send(embed=embed, view=CreateTicketView())

@bot.command()
async def init_leads(ctx):
    """Initialize the leads channel with the leads button"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Only administrators can run this command.")
        return
    
    if LEADS_CHANNEL_ID is None:
        await ctx.send("Run !setup first.")
        return
    
    channel = bot.get_channel(LEADS_CHANNEL_ID)
    await init_leads_internal(channel)
    await ctx.send("✓ Leads message sent.")

async def init_leads_internal(channel):
    embed = discord.Embed(
        title="Get Leads",
        description="Click the button below to receive leads.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed, view=GetLeadsView())

class CreateTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        tickets_category = bot.get_channel(TICKETS_CATEGORY_ID)
        caller_role = discord.utils.get(guild.roles, name=CALLER_ROLE)
        staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE)
        
        try:
            # Create a ticket channel for this user
            channel_name = f"user-{user.name}"
            ticket_channel = await guild.create_text_channel(
                channel_name,
                category=tickets_category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    caller_role: discord.PermissionOverwrite(view_channel=False),
                    staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
            )
            
            # Send application message with approval/denial buttons
            embed = discord.Embed(
                title="Application",
                description="1. Enter your name\n2. Can you work from 8am PST to 4pm PST?\n3. Submit a link to a video or voice message of you speaking english",
                color=discord.Color.blue()
            )
            
            msg = await ticket_channel.send(embed=embed, view=TicketFormView(user.id, ticket_channel.id))
            
            await interaction.response.send_message("✓ Ticket created! Check your new channel.", ephemeral=True)
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)
    
    @discord.ui.button(label="View Channels", style=discord.ButtonStyle.secondary)
    async def view_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        viewer_role = discord.utils.get(interaction.guild.roles, name=VIEWER_ROLE)
        
        if viewer_role:
            if viewer_role in user.roles:
                await user.remove_roles(viewer_role)
                await interaction.response.send_message("✓ Viewer role removed.", ephemeral=True)
            else:
                await user.add_roles(viewer_role)
                await interaction.response.send_message("✓ Viewer role added.", ephemeral=True)
        else:
            await interaction.response.send_message("Viewer role not found.", ephemeral=True)

class TicketFormView(discord.ui.View):
    def __init__(self, user_id, channel_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.channel_id = channel_id
    
    @discord.ui.button(label="✓ Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = await guild.fetch_member(self.user_id)
        caller_role = discord.utils.get(guild.roles, name=CALLER_ROLE)
        
        if caller_role:
            await user.add_roles(caller_role)
        
        await interaction.response.defer()
        
        # Delete the channel after a short delay
        ticket_channel = bot.get_channel(self.channel_id)
        if ticket_channel:
            await asyncio.sleep(1)
            await ticket_channel.delete()
    
    @discord.ui.button(label="✗ Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Delete the channel after a short delay
        ticket_channel = bot.get_channel(self.channel_id)
        if ticket_channel:
            await asyncio.sleep(1)
            await ticket_channel.delete()

class GetLeadsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Get Leads", style=discord.ButtonStyle.green)
    async def get_leads(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        user_id = user.id
        
        # Check cooldown
        if user_id in lead_cooldowns:
            last_press = lead_cooldowns[user_id]
            cooldown_end = last_press + timedelta(minutes=LEAD_BUTTON_TIMEOUT_MINUTES)
            if datetime.now() < cooldown_end:
                remaining = (cooldown_end - datetime.now()).total_seconds()
                await interaction.response.send_message(
                    f"⏱ You can get more leads in {int(remaining)} seconds.",
                    ephemeral=True
                )
                return
        
        # Update cooldown and count
        lead_cooldowns[user_id] = datetime.now()
        if user_id not in daily_lead_counts:
            daily_lead_counts[user_id] = 0
        daily_lead_counts[user_id] += 1
        
        guild = interaction.guild
        tickets_category = bot.get_channel(TICKETS_CATEGORY_ID)
        
        # Create a new channel for this lead ticket batch
        channel_name = f"lead-ticket-{user_id}-{int(datetime.now().timestamp())}"
        lead_channel = await guild.create_text_channel(
            channel_name,
            category=tickets_category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )
        
        # Build single message with all leads
        leads_text = "\n".join([
            f"**{i+1}. {lead['name']}**\nPhone: {lead['phone']}\nEmail: {lead['email']}\n"
            for i, lead in enumerate(SAMPLE_LEADS)
        ])
        
        embed = discord.Embed(
            title="Your Leads",
            description=leads_text,
            color=discord.Color.green()
        )
        
        msg = await lead_channel.send(embed=embed)
        lead_channel_messages[msg.id] = (user_id, lead_channel.id)
        await msg.add_reaction("❌")
        
        await interaction.response.send_message(f"✓ {len(SAMPLE_LEADS)} leads created in {lead_channel.mention}!", ephemeral=True)

@tasks.loop(time=time(23, 59))  # Run at 11:59 PM daily
async def daily_report():
    """Send daily report of lead button presses"""
    if DAILY_REPORT_CHANNEL_ID is None:
        return
    
    channel = bot.get_channel(DAILY_REPORT_CHANNEL_ID)
    
    embed = discord.Embed(
        title="Daily Lead Report",
        description=f"Report for {datetime.now().strftime('%Y-%m-%d')}",
        color=discord.Color.blue()
    )
    
    if daily_lead_counts:
        for user_id, count in daily_lead_counts.items():
            try:
                user = await bot.fetch_user(user_id)
                embed.add_field(name=user.mention, value=f"{count} leads requested", inline=False)
            except:
                embed.add_field(name=f"User {user_id}", value=f"{count} leads requested", inline=False)
    else:
        embed.description += "\n\nNo leads were distributed today."
    
    await channel.send(embed=embed)
    
    # Reset daily counts
    daily_lead_counts.clear()

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))