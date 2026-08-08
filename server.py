# pip install websockets
# pip install psycopg2-binary
# python "F:\Internet\Projects\Damka\server.py"
# not sleeping: uptimerobot.com

import asyncio
import json
import websockets # online server
import psycopg2 # data base (supabase.com)
from psycopg2 import errors

databaseUrl = "postgresql://postgres.ywiazghmzxtdflwirwrg:damkadatabase8339@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
playingPlayers = []
waitingPlayers = []


def signUp(username, password):
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password)
        )
        
        connection.commit()
        cursor.close()
        return True
    except errors.UniqueViolation:
        print("SignUp: Username already exists")
        if connection:
            connection.rollback()
        return False
    except Exception as e:
        print(f"SignUp Exception: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()

def logIn(username, password):
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT username FROM users WHERE username = %s AND password = %s", 
            (username, password)
        )
        user = cursor.fetchone()
        cursor.close()

        if user:
            return True
        print("LogIn: User or password incorrect")
        return False
        
    except Exception as e:
        print(f"LogIn Exception: {e}")
        if connection:
            connection.rollback()
        return False

    finally:
        if connection:
            connection.close()

def AddMatchToHistory(username, eats, result, isOnline, isSingle, myTurn, difficulty, enemyName):
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        
        # set all data
        matchType = False
        playerName = username
        if isOnline:
            matchType = "Online"
            if (result == "White" and myTurn == 0) or (result == "Black" and myTurn == 1):
                result = "WIN"
            elif (result == "White" and myTurn == 1) or (result == "Black" and myTurn == 0):
                result = "LOSE"
            else:
                result = "DRAW"

        elif isSingle:
            matchType = "Single-Player"
            if result == "White":
                result = "WIN"
            elif result == "Black":
                result = "LOSE"
            else:
                result = "DRAW"
            if difficulty == 1:
                enemyName = "Easy-AI"
            elif difficulty == 2:
                enemyName = "Medium-AI"
            elif difficulty == 3:
                enemyName = "Hard-AI"

        else:
            matchType = "Multiplayer"
            playerName = "White"
            enemyName = "Black"

        newMatch = json.dumps([{
            "MatchType": matchType,
            "Result": result,
            "Eats": eats,
            "PlayerName": playerName,
            "EnemyName": enemyName
        }])

        cursor.execute('''
            UPDATE users
            SET matches = (
                SELECT COALESCE(jsonb_agg(elem ORDER BY ord), '[]'::jsonb)
                FROM (
                    SELECT elem, ord
                    FROM jsonb_array_elements(COALESCE(matches, '[]'::jsonb) || %s::jsonb) WITH ORDINALITY AS t(elem, ord)
                    ORDER BY ord DESC
                    LIMIT 15
                ) sub
            )
            WHERE username = %s;
        ''', (newMatch, username))

        connection.commit()
        cursor.close()
        return True

    except Exception:
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()

def GetMatchesHistory(username):
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute('''
            SELECT matches 
            FROM users 
            WHERE username = %s;
        ''', (username,))

        row = cursor.fetchone()
        cursor.close()

        if row:
            history = row[0]
            return history
        return False

    except Exception as e:
        print(f"Error in GetMatchesHistory: {e}")
        return False
    finally:
        if connection:
            connection.close()


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
        print(f"Error in initDatabase: {e}")

initDatabase()

def clearDatabase():
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute("TRUNCATE TABLE users;")

        connection.commit()
        cursor.close()
        connection.close()
        print("Database cleared successfully!")
    except Exception as e:
        print("Error clearing database:", e)

#clearDatabase()


async def HandlePlayer(player):
    try:
        async for message in player:
            data = json.loads(message)
            action = data.get("Action")
            if action == "WaitingPlayer":
                playerUsername = data.get("Username")
                settings = data.get("Settings")
                playerData = [player, settings]
                enemy = False
                # try to find an enemy
                for enemyData in waitingPlayers:
                    sameSettings = True
                    enemySettings = enemyData[0][1]
                    # check if both players has the same settings
                    for name in enemySettings:
                        if enemySettings[name] != settings[name] and name != "Sounds":
                            sameSettings = False
                            break
                    if sameSettings:
                        enemy = enemyData[0][0]
                        break
                # if they have the same settings, take them into a game
                if enemy:
                    enemyUsername = enemyData[1]
                    waitingPlayers.remove(enemyData)
                    playingPlayers.append([player, enemy, playerUsername, enemyUsername, [0, 0]]) # add the players into game array
                    playerMessage = {
                        "Action": "StartGame",
                        "EnemyName": enemyUsername or "Guest",
                        "Turn": 1,
                    }
                    enemyMessage = {
                        "Action": "StartGame",
                        "EnemyName": playerUsername or "Guest",
                        "Turn": 0,
                    }
                    await player.send(json.dumps(playerMessage))
                    await enemy.send(json.dumps(enemyMessage))

                # if didnt find enemy, add to the waiting list
                else:
                    waitingPlayers.append([playerData, playerUsername])

            elif action == "UpdateEnemy":
                playersEats = data.get("PlayersEats")
                for match in playingPlayers:
                    if match[0] == player:
                        match[4] = playersEats
                        await match[1].send(message)
                        break
                    elif match[1] == player:
                        match[4] = playersEats
                        await match[0].send(message)
                        break
            
            elif action == "GameOver":
                for match in playingPlayers[:]:
                    if match[0] == player:
                        enemy = match[1]
                        playingPlayers.remove(match)
                        await enemy.send(message)
                        break
                    elif match[1] == player:
                        enemy = match[0]
                        playingPlayers.remove(match)
                        await enemy.send(message)
                        break

            elif action == "RemovePlayer":
                for playerData in waitingPlayers:
                    if playerData[0][0] == player:
                        waitingPlayers.remove(playerData)
                        break
            elif action == "SignUp":
                username = data.get("Username")
                password = data.get("Password")
                result = signUp(username, password)
                message = {
                    "Action": "SignUp",
                    "Username": username,
                    "Result": result
                }
                await player.send(json.dumps(message))
            elif action == "LogIn":
                username = data.get("Username")
                password = data.get("Password")
                result = logIn(username, password)
                history = GetMatchesHistory(username)
                message = {
                    "Action": "LogIn",
                    "Username": username,
                    "Result": result,
                    "History": history
                }
                await player.send(json.dumps(message))
            elif action == "AddMatch":
                username = data.get("Username")
                result = data.get("Result")
                eats = data.get("Eats")
                isOnline = data.get("IsOnline")
                isSingle = data.get("IsSingle")
                myTurn = data.get("MyTurn")
                difficulty = data.get("Difficulty")
                enemyName = data.get("EnemyName")
                result = AddMatchToHistory(username, eats, result, isOnline, isSingle, myTurn, difficulty, enemyName)
                if result:
                    matchesHistory = GetMatchesHistory(username)
                    if matchesHistory:
                        message = {
                            "Action": "UpdateMatchesHistory",
                            "Username": username,
                            "History": matchesHistory
                        }
                        await player.send(json.dumps(message))


    except websockets.exceptions.ConnectionClosedError:
        pass
    finally:
        # remove from waiting list
        for playerData in waitingPlayers:
            if playerData[0][0] == player:
                waitingPlayers.remove(playerData)
                break

        # if playing, save history data for both players
        for match in playingPlayers:
            if match[0] == player or match[1] == player:
                playerIndex = match.index(player)
                enemyIndex = 1 - playerIndex
                enemySocket = match[enemyIndex]
                
                playerUsername = match[2] if playerIndex == 0 else match[3]
                enemyUsername = match[3] if playerIndex == 0 else match[2]
                currentEats = match[4]
                playingPlayers.remove(match)
                
                winner = "White" if enemyIndex == 0 else "Black"
                loser = "White" if player == 0 else "Black"
                if playerUsername != "Guest":
                    myTurn = playerIndex
                    AddMatchToHistory(playerUsername, currentEats, loser, True, False, myTurn, 0, enemyUsername or "Guest")

                enemyMessage = {
                    "Action": "GameOver",
                    "Winner": winner
                }
                await enemySocket.send(json.dumps(enemyMessage))
                break

async def main():
    async with websockets.serve(HandlePlayer, "0.0.0.0", 10000):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())