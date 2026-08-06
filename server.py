# pip install websockets
# pip install psycopg2-binary
# python "F:\Internet\Projects\Damka\server.py"
# not sleeping: uptimerobot.com

import asyncio
import json
import websockets # online server
import psycopg2 # data base (supabase.com)
from psycopg2 import errors

databaseUrl = "postgresql://postgres:damkadatabase8339@db.ywiazghmzxtdflwirwrg.supabase.co:5432/postgres"
playingPlayers = []
waitingPlayers = []


def signUp(username, password):
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password)
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except errors.UniqueViolation:
        if connection:
            connection.rollback()
        return False
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error: {e}")
        return False
    finally:
        if connection:
            connection.close()

def logIn(username, password):
    try:
        conn = psycopg2.connect(databaseUrl)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE username = %s AND password_hash = %s", (username, password)
        )
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            return True
        return False
       
    except Exception:
        return False


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
            elif action == "SignUp":
                username = data.get("Username")
                password = data.get("Password")
                result = signUp(username, password)
                message = {
                    "Action": "SignUp",
                    "Result": result
                }
                player.send(json.dumps(message))



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
    async with websockets.serve(HandlePlayer, "0.0.0.0", 10000):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())


def initDatabase():
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(20) NOT NULL,
                matches JSONB DEFAULT '[]'::jsonb
            );
        ''')

        connection.commit()
        cursor.close()
        connection.close()
        print("Database initialized successfully!")
    except Exception as e:
        print("Error connecting to Database:", e)

initDatabase()