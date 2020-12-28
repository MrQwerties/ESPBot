from discord import Embed, Intents
from discord.ext.commands import Bot, CommandError, dm_only
from discord.utils import get

from datetime import datetime, timedelta
from email.mime.text import MIMEText
from json import load
from secrets import token_hex
from smtplib import SMTP_SSL
from typing import Optional

import csv


with open("config.json") as fp:
    Config = load(fp)


def get_email(username):
    with open(Config["csv"]["students"], "r") as csvfile:
        studentreader = csv.DictReader(csvfile)
        for row in studentreader:
            row_names = row["username"].split(",")
            if username in row_names:
                return row["email"].split(",")[row_names.index(username)], True
    with open(Config["csv"]["teachers"], "r") as csvfile:
        studentreader = csv.DictReader(csvfile)
        for row in studentreader:
            row_names = row["username"].split(",")
            if username in row_names:
                return row["email"].split(",")[row_names.index(username)], False
    return None, True


def sent_email(username):
    with open(Config["csv"]["tokens"], "r") as csvfile:
        tokenreader = csv.DictReader(csvfile)
        for row in tokenreader:
            if row["username"].lower() == username.lower():
                return True
    return False


def check_token(username, token):
    with open(Config["csv"]["tokens"], "r") as csvfile:
        tokenreader = csv.DictReader(csvfile)
        for row in tokenreader:
            if row["username"].lower() == username.lower() and row["token"] == token:
                return True
    return False


def save_token(username, token):
    with open(Config["csv"]["tokens"], "a") as csvfile:
        fieldnames = ["username", "token"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow({"username": username, "token": token})


async def finish_verification(ctx, is_student):
    guild = ctx.bot.get_guild(Config["discord"]["guild"])
    members = await guild.query_members(user_ids=[ctx.message.author.id])
    await members[0].add_roles(
        guild.get_role(
            Config["discord"]["student_role" if is_student else "teacher_role"]
        )
    )
    embed = generate_embed_template(ctx, "Account Verified Successfully")
    embed.description = "Contact the admins if you still can't access the server."
    await ctx.send(embed=embed)


def generate_embed_template(ctx, title, error=False):
    embed = Embed(colour=16711680 if error else 32768, title=title)
    embed.timestamp = datetime.utcnow()
    embed.set_author(name=str(ctx.author), icon_url=str(ctx.author.avatar_url))
    embed.set_footer(text=str(ctx.me), icon_url=str(ctx.me.avatar_url))
    return embed


class AdmitBot(Bot):
    def __init__(self):
        intents = Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", help_command=None, intents=intents)

    async def on_command_error(self, ctx, exception):
        embed = generate_embed_template(ctx, "Error running command", True)
        embed.description = (
            ("Please type !verify, followed by a space, then your username.")
            if "is not found" in str(exception)
            else str(exception)
        )
        await ctx.send(embed=embed)

    async def on_member_join(self, member):
        if not get(member.roles, id=Config["discord"]["student_role"]) and not get(
            member.roles, id=Config["discord"]["teacher_role"]
        ):
            embed = Embed(
                colour=32768, title="Welcome to the Splash 2020 Discord Server!"
            )
            embed.timestamp = datetime.utcnow()
            embed.set_author(name=str(member), icon_url=str(member.avatar_url))
            embed.set_footer(text=str(self.user), icon_url=str(self.user.avatar_url))
            embed.description = (
                "Please type `!verify <username>` below, for whatever username you used in "
                "the ESP website. I will then email you a verification code to send back to me. It may take a "
                "little bit of time to be delivered (especially if you use Yahoo!, for some reason), "
                "but it should get there.\n\n Once you receive the email, please copy/paste the "
                "verification command and alphanumeric string back here, in the message field below. "
                "If, for some reason, you have continued trouble gaining access to the server, please"
                "contact `splash@mit.edu` to assist.\n\n"
            )
            await member.send(embed=embed)


bot = AdmitBot()


@bot.command(name="help")
async def help_command(ctx):
    embed = generate_embed_template(ctx, "Email Address Verification")
    embed.description = (
        "```!verify <username> [token]```\n\n"
        "`!verify` is used to verify your Discord account with your ESP website username before you are given "
        "access to the Discord server. To use the command, run `!verify` with your username to request a "
        "verification token that will be sent to your email inbox. That email will give you the token needed to "
        "complete your account verification and give you full access to the server.\n\nIf you are already "
        "verified, running `!verify` with your username will give you the role for full access to the server "
        "again in case you do not have it. If you have continued trouble gaining access to the server, please "
        "contact `splash@mit.edu` to assist."
    )
    await ctx.send(embed=embed)


@bot.command(name="verify")
@dm_only()
async def verify(ctx, username: str, token: Optional[str]):
    email, is_student = get_email(username)
    if email is not None:
        if token:
            if check_token(username, token):
                await finish_verification(ctx, is_student)
                return
            else:
                raise CommandError(
                    "Token is incorrect! Double check and make sure it is correct."
                )
        elif sent_email(username):
            raise CommandError(
                "We already sent an email to this username! If you don't get the email "
                "within a few minutes, please email us at `splash@mit.edu` with your "
                "username on the website and on Discord."
            )
        else:
            gen = token_hex(32)
            smtp = SMTP_SSL(Config["smtp"]["outgoing"])
            smtp.login(Config["smtp"]["username"], Config["smtp"]["password"])
            msg = MIMEText(
                "Hello!<br><br>\n"
                + "To verify your email address, please send the following command to the bot:"
                + f"<br>\n<pre>!verify {username} {gen}</pre><br><br>\n"
                + "If you didn't request this verification, please ignore this email.",
                "html",
            )
            msg["Subject"] = "Verification for Splash 2020 Discord Server"
            msg["From"] = "Splash Discord Verifier <splash@mit.edu>"
            msg["To"] = email
            smtp.sendmail("splash@mit.edu", email, msg.as_string())
            embed = generate_embed_template(ctx, "Verification Requested Successfully")
            embed.description = f"Please check your inbox for further instructions."
            save_token(username, gen)
            await ctx.send(embed=embed)
            return
    else:
        raise CommandError(
            "We don't appear to have a user with that username. Please check that you typed your username "
            "correctly. If this still doesn't work, please email us at `splash@mit.edu` with your username "
            "on the website and on Discord."
        )


bot.run(Config["discord"]["token"])
