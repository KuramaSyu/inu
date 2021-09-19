import discord


async def information_message(channel, info, del_after = 30, user = None, small = False, title = 'Info:', 
                            color : discord.Color = discord.Color.from_rgb(150,150,150),
                            thumbnail_ = None):
    information_embed = discord.Embed(
    #title='Aktuelles Lied:',
    #description=f'{self.board_description}',
    colour=color
    )
    if user:
        information_embed.set_author(name = user.name, icon_url = user.avatar_url)
    if thumbnail_:
        information_embed.set_thumbnail(url=str(thumbnail_))
    if not small:
        information_embed.add_field(name = f'{title}', value=f'{info}', inline=True)
        if del_after:
            information_embed.set_footer(text = f'This message will be deleted in {del_after} seconds')
    else:
        information_embed.description = f'{info}'
    if del_after:
        await channel.send(embed = information_embed, delete_after = int(del_after))
    else:
        await channel.send(embed = information_embed)