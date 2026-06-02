# pip install websockets
# python "F:\Internet\Projects\Damka\server.py"

import asyncio
from asyncio.windows_events import NULL
from genericpath import samestat
import json
import websockets

playingPlayers = []
waitingPlayers = []

async def HandlePlayer(player):
    try:
        async for message in player:
            data = json.loads(message)
            action = data.get("Action")
            if action == "WaitingPlayer":
                settings = data.get("Settings")
                playerData = [player, settings]
                enemy = False
                # try to find an enemy
                for enemyData in waitingPlayers:
                    sameSettings = True
                    enemySettings = enemyData[1]
                    # check if both players has the same settings
                    for name in enemySettings:
                        if enemySettings[name] != settings[name] and name != "Sounds":
                            sameSettings = False
                            break
                    if sameSettings:
                        enemy = enemyData[0]
                        break
                # if they have the same settings, take them into a game
                if enemy:
                    waitingPlayers.remove(enemyData)
                    playingPlayers.append([player, enemy]) # add the players into game array
                    playerMessage = {
                        "Action": "StartGame",
                        "Turn": 1,
                    }
                    enemyMessage = {
                        "Action": "StartGame",
                        "Turn": 0,
                    }
                    await player.send(json.dumps(playerMessage))
                    await enemy.send(json.dumps(enemyMessage))

                # if didnt find enemy, add to the waiting list
                else:
                    waitingPlayers.append(playerData)

            elif action == "UpdateEnemy":
                # find the enemy
                for match in playingPlayers:
                    for i in range(len(match)):
                        if match[i] == player:
                            enemy = match[1 - i]
                            await enemy.send(message)
            
            elif action == "GameOver":
                for match in playingPlayers:
                    for i in range(len(match)):
                        if match[i] == player:
                            enemy = match[1 - i]
                            playingPlayers.remove(match)
                            await enemy.send(message)

            elif action == "RemovePlayer":
                for playerData in waitingPlayers:
                    if playerData[0] == player:
                        waitingPlayers.remove(playerData)


    except websockets.exceptions.ConnectionClosedError:
        pass
    finally:
        # remove from witing list
        for playerData in waitingPlayers:
            if playerData[0] == player:
                waitingPlayers.remove(playerData)

        # if in a match, send draw to the enemy and remove from list
        for match in playingPlayers:
            for i in range(len(match)):
                if match[i] == player:
                    enemy = match[1 - i]
                    playingPlayers.remove(match)
                    enemyMessage = {
                        "Action": "GameOver",
                        "Winner": "Draw"
                    }
                    await enemy.send(json.dumps(enemyMessage))

async def main():
    async with websockets.serve(HandlePlayer, "localhost", 1234):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())