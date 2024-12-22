import os
import re
import discord
from discord import app_commands
import requests
from keep_alive import keep_alive

CONFIG = {
    'API_KEY': 'onEkoztnFpTi3VG7XQEq6skQWN3aFm3h',
    'API_URL': 'https://production-archive-proxy-api.lightspeedsystems.com/archiveproxy',
    'UNBLOCKED': [5, 6, 9, 14, 15, 18, 20, 30, 36, 43, 44, 46, 47, 48, 49, 50, 57, 68, 74, 75, 76, 77, 83, 85, 95, 99, 128, 129, 131, 132, 140, 900],
    'BATCH_SIZE': 2
}

def clean_domain(url):
    domain = re.sub(r'https?://', '', url.strip().lower())
    domain_parts = domain.split('/', 1)
    domain = domain_parts[0]
    return domain

def validate_domain(domain):
    domain = clean_domain(domain)
    pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*(?:\.[a-zA-Z]{2,})$'
    return bool(re.match(pattern, domain))

async def process_domains(domains):
    results = []
    for domain_a in domains:
        domain_a = clean_domain(domain_a)
        query = """
            query getDeviceCategorization($itemA: CustomHostLookupInput!) {
                a: custom_HostLookup(item: $itemA) {
                    request {
                        host
                    }
                    archive_info {
                        filter {
                            category
                        }
                    }
                }
            }
        """
        variables = {'itemA': {'hostname': domain_a, 'getArchive': True}}
        payload = {'query': query, 'variables': variables}

        try:
            response = requests.post(
                CONFIG['API_URL'],
                json=payload,
                headers={'Content-Type': 'application/json', 'X-API-Key': CONFIG['API_KEY']},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if 'errors' in data:
                raise requests.exceptions.RequestException(f"API Error: {data['errors']}")

            if data.get('data', {}).get('a'):
                domain_info = data['data']['a']
                domain = domain_info['request']['host']
                category = domain_info['archive_info']['filter']['category']
                status = "UNBLOCKED" if category in CONFIG['UNBLOCKED'] else "BLOCKED"
                domain = clean_domain(domain)
                results.append({'domain': domain, 'status': status, 'category': category})
            else:
                results.append({'domain': domain_a, 'status': 'ERROR', 'category': None})
        except requests.exceptions.RequestException as error:
            results.append({'domain': domain_a, 'status': 'ERROR', 'category': None})

    return results

class lol(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = lol()

@client.tree.command(name="check", description="Check the status of a domain")
async def check(interaction: discord.Interaction, domain: str):
    await interaction.response.defer(ephemeral=True)

    cleaned_domain = clean_domain(domain)
    if not validate_domain(cleaned_domain):
        await interaction.followup.send("❌ Invalid domain format.")
        return

    results = await process_domains([cleaned_domain])

    if not results:
        await interaction.followup.send("❌ Error processing domain.")
        return

    result = results[0]
    status_color = {
        'BLOCKED': discord.Color.red(),
        'UNBLOCKED': discord.Color.green(),
        'ERROR': discord.Color.yellow()
    }.get(result['status'], discord.Color.default())

    embed = discord.Embed(
        title="Domain Check Result",
        color=status_color
    )
    embed.add_field(name="Domain", value=result['domain'], inline=False)
    embed.add_field(name="Status", value=result['status'], inline=True)
    embed.add_field(name="Category", value=str(result['category'] if result['category'] else 'N/A'), inline=True)

    await interaction.followup.send(embed=embed)

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

from keep_alive import keep_alive
keep_alive()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    raise ValueError("No token found. Please set the DISCORD_BOT_TOKEN environment variable.")
client.run(TOKEN)
