if __name__ == '__main__':
    from . import Kamisato

    bot = Kamisato()
    bot.run(bot.config['discord']['token'])
