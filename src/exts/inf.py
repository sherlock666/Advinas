import re
import time
import slash_util
import discord
from discord.ext import commands
from discord.ext.commands import Context
from bot import Advinas
from math import floor, ceil
from typing import Union
from exts.database import Database
from infinitode.models import Leaderboard, Score
from common.images import Images
from common.views import Paginator, ScorePaginator
from common.source import LBSource, ScoreLBSource
from common.utils import (
    BadChannel,
    answer,
    round_to_nearest,
    find_safe,
    get_level,
    get_level_bounty,
    codeblock,
    log,
    tablify,
    load_json
)


class Inf(slash_util.Cog):
    def __init__(self, bot: Advinas):
        super().__init__(bot)
        self.bot: Advinas
        self.mention_regex = re.compile(r'<@!?([0-9]+)>')
        self.playerid_regex = re.compile(
            r'U-([A-Z0-9]{4}-){2}[A-Z0-9]{6}')
        inf = load_json("data/inf.json")
        self.LEVELS: list[str] = list(inf['levels'].keys())
        self.LEVEL_INFO: dict[str: dict] = inf['levels']
        self.BOUNTY_DIFFS: dict[str: int] = inf['bountyDifficulties']
        self.EMOJIS: dict[str: int] = inf['enemy_emojis']
        self.images = Images()

    async def cog_check(self, ctx) -> bool:
        if ctx.guild and ctx.guild.id == 590288287864848387:
            if ctx.channel.id not in self.bot.BOT_CHANNELS:
                raise BadChannel('Command not used in an allowed channel.')
        return True

    async def slash_command_error(self, ctx, error: Exception) -> None:
        await self.bot.on_command_error(ctx, err=error)

    # Score command
    @slash_util.slash_command(name='score')
    async def _score(self, ctx: slash_util.Context, level: str):
        '''Shows the top 200 scores of the given level.'''
        await self.cog_check(ctx)
        await self.score(ctx, level=level)

    @commands.command(name='score', aliases=['s'])
    async def score(self, ctx: Union[Context, slash_util.Context], level: str):
        level = get_level(self.LEVELS, level)
        normal = await self.bot.API.leaderboards(level)
        endless = await self.bot.API.leaderboards(level, difficulty='ENDLESS_I')
        await log(ctx)
        await ScorePaginator(ScoreLBSource(normal, endless, f'Level {level} Leaderboards (Score)', ctx)).start(ctx)

    # Wave command
    @slash_util.slash_command(name='waves')
    async def _waves(self, ctx: slash_util.Context, level: str):
        '''Shows the top 200 waves of the given level.'''
        await self.cog_check(ctx)
        await self.waves(ctx, level=level)

    @commands.command(name='waves', aliases=['w'])
    async def waves(self, ctx: Union[Context, slash_util.Context], level: str):
        level = get_level(self.LEVELS, level)
        normal = await self.bot.API.leaderboards(level, mode='waves')
        endless = await self.bot.API.leaderboards(level, mode='waves', difficulty='ENDLESS_I')
        await log(ctx)
        await ScorePaginator(ScoreLBSource(normal, endless, f'Level {level} Leaderboards (Waves)', ctx)).start(ctx)

    # Season command
    @slash_util.slash_command(name='season')
    async def _season(self, ctx: slash_util.Context):
        '''Shows the top 100 players of the season.'''
        await self.cog_check(ctx)
        await self.season(ctx)

    @commands.command(name='season', aliases=['sl', 'seasonal'])
    async def season(self, ctx: Union[Context, slash_util.Context]):
        lb = await self.bot.API.seasonal_leaderboard()
        await log(ctx)
        await Paginator(LBSource(lb, f'Season {lb.season} Leaderboards', ctx, headline=f'Player Count: {lb.total}')).start(ctx)

    # Dailyquest command
    @slash_util.slash_command(name='dailyquest')
    async def _dailyquest(self, ctx: slash_util.Context, date: str = None):
        '''Shows the top dailyquest scores of today or the given the day.'''
        await self.cog_check(ctx)
        await self.dailyquest(ctx, date=date)

    @commands.command(name='dailyquest', aliases=['dq'])
    async def dailyquest(self, ctx: Union[Context, slash_util.Context], date: str = None):
        lb, date = await self.bot.API.daily_quest_leaderboards(date, warning=False, return_date=True)
        if lb.is_empty:
            entry = Database.find_by_key(self.bot.DB.dailyquests, date)
            try:
                scores = entry.get(date, None)
                lb = Leaderboard('', '', '', '', '', date=date)
                for score in scores:
                    lb._append(Score('', '', '', '', **score))
            except:
                await log(ctx, success=False, reason='Invalid date provided.')
                return await answer(ctx, content='Could not find anything for that date. Sorry.')

        await log(ctx)
        await Paginator(LBSource(lb, f'Dailyquest Leaderboards ({date})', ctx)).start(ctx)

    # Level command
    @slash_util.slash_command(name='level')
    async def _level(self, ctx: slash_util.Context, level: str):
        '''Shows useful information about the given level.'''
        await self.cog_check(ctx)
        await ctx.defer()
        await self.level(ctx, level=level)

    @commands.command(name='level', aliases=['l'])
    async def level(self, ctx: Union[Context, slash_util.Context], level: str):
        level = get_level(self.LEVELS, level)
        data = self.LEVEL_INFO[level.lower(
        ) if level.startswith('DQ') else level]
        enemy_emojis = "".join(
            [f'<:enemy_{i.lower()}:{self.EMOJIS[f"enemy_{i.lower()}"]}>' for i in data["enemies"]])
        enemy_emojis = enemy_emojis or "None"
        filename = f'{level}.png'
        file = discord.File(f'assets/images/levels/{filename}')
        base = tablify(data["base"])
        quests = tablify(data["quests"])

        em = discord.Embed(title=f"Level {level} Info", colour=60415)
        em.set_image(url=f"attachment://{filename}")
        em.add_field(name="Difficulty", value=f"{data['difficulty']}%", inline=True)  # nopep8
        em.add_field(name="Enemies", value=enemy_emojis, inline=True)
        em.set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        try:
            rt_lb = await self.bot.API.runtime_leaderboards(level, "U-T68Z-T3JV-HK3DJY")
            em.add_field(name="Top 1% Threshold", value="{:,}".format(int(rt_lb[200].score)))  # nopep8
        except:
            pass
        if base:
            em.add_field(name="Base Effects", value=base, inline=False)
        if quests:
            em.add_field(name="Quest Effects", value=quests, inline=False)

        await answer(ctx, embed=em, file=file)
        await log(ctx)

    # Bounty command
    @slash_util.slash_command(name='bounty')
    async def _bounty(self, ctx: slash_util.Context, coins: int = 65, difficulty: float = 100, bounties: int = 7, level: str = None):
        '''Calculates the optimal timings to place your bounties.'''
        await self.cog_check(ctx)
        await self.bounty(ctx, coins=coins, difficulty=difficulty, bounties=bounties, level=level)

    @commands.command(name='bounty', aliases=['b'])
    async def bounty(self, ctx: Union[Context, slash_util.Context], coins: int = 65, difficulty: float = 100, bounties: int = 7, level: str = None):
        level, difficulty, bounties, coins = get_level_bounty(
            self.BOUNTY_DIFFS, level=level, difficulty=difficulty, bounties=bounties, coins=coins)
        keep = coins * 50
        difSlope = 1+((difficulty-100)/200)
        lBounties, lCost, lBuy = [], [], []
        for i in range(1, bounties+1):
            val = floor((difSlope) * (1.60000002384186 **
                        (1.15 * (i - 1)) * 180))
            if val < 500:
                cost = round_to_nearest(val, 5)
            elif val < 5000:
                cost = round_to_nearest(val, 10)
            else:
                cost = round_to_nearest(val, 50)
            if (cost * i) < (coins * 50):
                buy = int((ceil(cost * (i - 1) / 50) * 50) + cost)
            else:
                buy = int((ceil(coins * (i - 1) / i) * 50) + cost)
            lBounties.append(str(i))
            lCost.append(str(cost))
            lBuy.append(str(find_safe(i=i, buy=buy, cost=cost, coins=coins)))

        description = f'Coins: `{coins}`\nDifficulty: `{difficulty}`\nKeepForMax: `{keep}`'
        if level:
            description += f'\nLevel: `{level}`'

        em = discord.Embed(
            title="Bounty Calculator", description=description, colour=60415
        ).set_footer(
            text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url
        ).add_field(
            name="Bounty", value=codeblock('\n'.join(lBounties)), inline=True
        ).add_field(
            name="Cost", value=codeblock('\n'.join(lCost)), inline=True
        ).add_field(
            name="Safe Buy", value=codeblock('\n'.join(lBuy)), inline=True)

        await answer(ctx, embed=em)
        await log(ctx)

    # Profile command
    @slash_util.slash_command(name='profile')
    async def _profile(self, ctx: slash_util.Context, playerid: str = None):
        '''Shows your in game profile in an image (NO ENDLESS LEADERBOARD DUE TO API LIMITATIONS).'''
        await self.cog_check(ctx)
        await ctx.defer()
        await self.profile(ctx, playerid=playerid)

    @commands.command(name='profile', aliases=['p'])
    async def profile(self, ctx: Union[Context, slash_util.Context], playerid: str = None):
        dc_col, nn_col = self.bot.DB.discordnames, self.bot.DB.nicknames
        pl, player = None, None
        start_time = time.time()
        if not playerid:
            pl = Database.find(dc_col, str(ctx.author.id)
                               ) or Database.find(nn_col, ctx.author.display_name
                                                  ) or Database.find(nn_col, ctx.author.name)
            if pl:
                player = await self.bot.API.player(playerid=next(iter(pl)))
            else:
                await log(ctx, success=False, reason='No player provided.')
                return await answer(ctx, content='Provide a player to search for.')
        elif self.playerid_regex.match(playerid):
            try:
                player = await self.bot.API.player(playerid=playerid)
            except:
                pass
            else:
                pl = {player.playerid: "<3"}
        if not player:
            pl = Database.find(nn_col, playerid)
            if not pl:
                match = self.mention_regex.search(playerid)
                new_id = match[0] if match else playerid
                pl = Database.find(dc_col, new_id)
                if not pl:
                    member = discord.utils.get(self.bot.users, name=playerid)
                    if member:
                        pl = Database.find(dc_col, str(member.id))
                    if not pl:
                        await log(ctx, success=False, reason='The provided player is invalid.')
                        return await answer(ctx, content='Could not find player. Check for spelling mistakes or try using '
                                            'the U- playerid from your profile page (Top left in the main menu).')
        if not player:
            player = await self.bot.API.player(playerid=next(iter(pl)))
        data = {player.playerid: {'name': player.nickname, 'key': player.nickname.lower()}}  # nopep8
        Database.update(nn_col, data=data)
        try:
            r = await self.bot.SESSION.get(player.avatar_link)
            r.raise_for_status()
            avatar_bytes = await r.read()
        except:
            avatar_bytes = None
        await player._get_daily_quest(self.bot.API)
        await player._get_skill_point(self.bot.API)

        final_buffer = await self.bot.loop.run_in_executor(None, self.images.profile_gen, player, avatar_bytes, ctx.author.id)

        file = discord.File(filename=f'{player.playerid}.png', fp=final_buffer)
        await answer(ctx, content=f'Finished in {time.time() - start_time:0.3f}s', file=file)
        await log(ctx)


def setup(bot):
    bot.add_cog(Inf(bot))
