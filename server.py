# pip install websockets
# pip install psycopg2-binary
# python "F:\Internet\Projects\Damka\server.py"
# not sleeping: uptimerobot.com

import asyncio
import json
import websockets # online server
import psycopg2 # data base (supabase.com)

databaseUrl = "postgresql://postgres.ywiazghmzxtdflwirwrg:damkadatabase8339@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
requestPlayers = {}
players = {}
admins = []
playingPlayers = []
waitingPlayers = []

def isUsernameTaken(cursor, username):
    cursor.execute('''
        SELECT 1 FROM users WHERE username = %s
        UNION
        SELECT 1 FROM pending_users WHERE username = %s
    ''', (username, username))
    return cursor.fetchone() is not None

def getPendingUsers():
    connection = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute("SELECT username, password FROM pending_users;")
        
        pending_list = cursor.fetchall()
        
        cursor.close()
        return pending_list

    except Exception:
        return []

    finally:
        if connection:
            connection.close()

def signUpRequest(username, password):
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        if isUsernameTaken(cursor, username):
            return False
        cursor.execute(
            "INSERT INTO pending_users (username, password) VALUES (%s, %s)",
            (username, password)
        )

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

def SignUp(username, isAccepted, socket):
    connection = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        if isAccepted:
            players[username] = socket
            cursor.execute("""
                INSERT INTO users (username, password)
                SELECT username, password
                FROM pending_users
                WHERE username = %s;
            """, (username,))

        cursor.execute("DELETE FROM pending_users WHERE username = %s;"
                , (username,))

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

async def logIn(username, password, socket):
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT is_admin FROM users WHERE username = %s AND password = %s", 
            (username, password)
        )
        user = cursor.fetchone()
        cursor.close()
        if user is not None:
            players[username] = socket
            if user[0]:
                admins.append(socket)
                globalHistory = GetGlobalHistory()
                message = {
                    "Action": "UpdateGlobalHistory",
                    "History": globalHistory,
                }
                await socket.send(json.dumps(message))
                return "Admin"
            return True
        return False
        
    except Exception as e:
        print(f"Error in logIn: {e}")
        if connection:
            connection.rollback()
        return False

    finally:
        if connection:
            connection.close()

def DeleteUser(username):
    connection = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute("DELETE FROM users WHERE username = %s;"
                , (username,))
        result = cursor.rowcount > 0 or "WrongUsername"

        connection.commit()
        cursor.close()
        return result

    except Exception:
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()

def IsAdmin(username):
    connection = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT is_admin FROM users WHERE username = %s
        """, (username,))

        result = cursor.fetchone()
        cursor.close()

        if result is not None:
            return result[0]
        return None

    except Exception:
        if connection:
            connection.rollback()
        return None
    finally:
        if connection:
            connection.close()

def ManageAdmin(username, isAdmin):
    connection = None
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE users
            SET is_admin = %s
            WHERE username = %s;
        """, (isAdmin, username))

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

    except Exception:
        return False
    finally:
        if connection:
            connection.close()

def GetGlobalHistory():
    connection = False
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute('''
            SELECT player1_name, player1_eats,
                   player2_name, player2_eats,
                   winner
            FROM global_history
            ORDER BY id DESC
            LIMIT 20;
        ''')
        rows = cursor.fetchall()
        cursor.close()

        history = []
        for row in rows:
            history.append({
                "Player1Name": row[0],
                "Player1Eats": row[1],
                "Player2Name": row[2],
                "Player2Eats": row[3],
                "Winner": row[4]
            })
        return history

    except Exception:
        return False
    finally:
        if connection:
            connection.close()

async def AddMatchToHistory(username, eats, result, isOnline, isSingle, myTurn, difficulty, enemyName):
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

        if isOnline and myTurn == 0: # add only one time, for the first player (dosent matter which player)
            if result == "WIN":
                winnerName = playerName
            elif result == "LOSE":
                winnerName = enemyName
            else:
                winnerName = "DRAW"

            cursor.execute('''
                INSERT INTO global_history (player1_name, player1_eats, player2_name, player2_eats, winner)
                VALUES (%s, %s, %s, %s, %s);
            ''', (playerName, eats[0], enemyName, eats[1], winnerName))

            cursor.execute('''
                DELETE FROM global_history
                WHERE id NOT IN (
                    SELECT id FROM global_history
                    ORDER BY id DESC
                    LIMIT 20
                );
            ''')
            connection.commit()

            # update admins
            globalHistory = GetGlobalHistory()
            message = {
                "Action": "UpdateGlobalHistory",
                "History": globalHistory,
            }
            for admin in admins:
                await admin.send(json.dumps(message))

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

def initDatabase():
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(20) UNIQUE NOT NULL,
                password VARCHAR(20) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                matches JSONB DEFAULT '[]'::jsonb
            );

            CREATE TABLE IF NOT EXISTS pending_users (
                username VARCHAR(20) UNIQUE NOT NULL,
                password VARCHAR(20) NOT NULL
            );

           CREATE TABLE IF NOT EXISTS global_history (
               id SERIAL PRIMARY KEY,
               player1_name VARCHAR(20) NOT NULL,
               player1_eats INTEGER DEFAULT 0,
               player2_name VARCHAR(20) NOT NULL,
               player2_eats INTEGER DEFAULT 0,
               winner VARCHAR(20) NOT NULL
           );
        ''')
        connection.commit()
        cursor.close()
        connection.close()
        print("database running")
    except Exception as e:
        print(f"Error in initDatabase: {e}")

initDatabase()

def inspectTables():
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        tables = ['users', 'pending_users', 'global_history']

        for table in tables:
            print(f"--- Table: {table} ---")

            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s;
            """, (table,))
            columns = cursor.fetchall()
            print("Columns:", [col[0] for col in columns])

            cursor.execute(f"SELECT * FROM {table};")
            rows = cursor.fetchall()
            print("Data:", rows)
            print()

        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inspecting database: {e}")

#inspectTables()

def resetDatabase():
    try:
        connection = psycopg2.connect(databaseUrl)
        cursor = connection.cursor()

        cursor.execute("DROP TABLE IF EXISTS global_history CASCADE;")

        connection.commit()
        cursor.close()
        connection.close()
        print("Database reseted successfully!")
    except Exception as e:
        print(f"Error dropping table: {e}")

#resetDatabase()

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
                    playingPlayers.append([enemy, player, playerUsername, enemyUsername, [0, 0]]) # add the players into game array
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
            elif action == "SignUpRequest":
                username = data.get("Username")
                password = data.get("Password")
                result = signUpRequest(username, password)
                requestPlayers[username] = player
                message = {
                    "Action": "SignUpRequest",
                    "Username": username,
                    "Result": result
                }
                await player.send(json.dumps(message))
                if result:
                    for admin in admins:
                        message = {
                        "Action": "NewRequest",
                        "Username": username,
                    }
                    await admin.send(json.dumps(message))
            elif action == "SignUp":
                username = data.get("Username")
                isAccepted = data.get("IsAccepted")
                socket = requestPlayers.get(username)
                result = SignUp(username, isAccepted, socket)
                requestPlayers.pop(username, None) # if not exits, return None and prevent error
                adminMessage = {
                    "Action": "SignUpResult",
                    "Username": username,
                    "IsAccepted": isAccepted,
                    "Result": result
                }
                await player.send(json.dumps(adminMessage))
                message = {
                    "Action": "SignUp",
                    "Username": username,
                    "IsAccepted": isAccepted,
                    "Result": result
                }
                try:
                    await socket.send(json.dumps(message))
                except:
                    pass
            elif action == "LogIn":
                username = data.get("Username")
                password = data.get("Password")
                result = await logIn(username, password, player)
                history = GetMatchesHistory(username)
                pendingUsers = False
                if result == "Admin":
                    pendingUsers = [user[0] for user in getPendingUsers()] # get all pending usernames in array
                message = {
                    "Action": "LogIn",
                    "Username": username,
                    "Result": result,
                    "History": history,
                    "PendingUsers": pendingUsers
                }
                await player.send(json.dumps(message))
            elif action == "DeleteUser":
                username = data.get("Username")
                result = DeleteUser(username)
                adminMessage = {
                    "Action": "DeleteResult",
                    "Username": username,
                    "Result": result
                }
                await player.send(json.dumps(adminMessage))
                message = { "Action": "DeleteUser"}
                try: 
                    await players[username].send(json.dumps(message))
                except:
                    pass
            elif action == "SearchAdmin":
                username = data.get("Username")
                result = IsAdmin(username)
                message = {
                    "Action": "SearchAdminResult",
                    "Username": username,
                    "Result": result,
                }
                await player.send(json.dumps(message))
            elif action == "ManageAdmin":
                username = data.get("Username")
                isAdmin = data.get("IsAdmin")
                result = ManageAdmin(username, isAdmin)
                adminMessage = {
                    "Action": "ManageAdminResult",
                    "IsAdmin": isAdmin,
                    "Result": result
                }
                message = {
                    "Action": "UserAdminResult",
                    "IsAdmin": isAdmin,
                    "Result": result
                }
                await player.send(json.dumps(adminMessage))
                try: 
                    userSocket = players[username]
                    if isAdmin:
                        admins.append(userSocket)
                    else:
                        admins.remove(userSocket)
                    await userSocket.send(json.dumps(message))
                except:
                    pass
            elif action == "AddMatch":
                username = data.get("Username")
                result = data.get("Result")
                eats = data.get("Eats")
                isOnline = data.get("IsOnline")
                isSingle = data.get("IsSingle")
                myTurn = data.get("MyTurn")
                difficulty = data.get("Difficulty")
                enemyName = data.get("EnemyName")
                result = await AddMatchToHistory(username, eats, result, isOnline, isSingle, myTurn, difficulty, enemyName)
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
        # delete from players array
        for username, socket in list(players.items()):
            if socket == player:
                del players[username]
                break

        # delete from request players array
        for username, socket in list(requestPlayers.items()):
            if socket == player:
                del requestPlayers[username]
                break

        # remove from admins array if he is admin
        if player in admins:
            admins.remove(player)

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
                
                playerUsername = match[3] if playerIndex == 0 else match[2]
                enemyUsername = match[2] if playerIndex == 0 else match[3]
                currentEats = match[4]
                playingPlayers.remove(match)

                winnerColor = "White" if enemyIndex == 0 else "Black"
                if playerUsername != "Guest":
                    myTurn = playerIndex
                    oppositeEats = currentEats if playerIndex == 0 else [currentEats[1], currentEats[0]] # opposite eats if black player
                    await AddMatchToHistory(playerUsername, oppositeEats, winnerColor, True, False, myTurn, 0, enemyUsername or "Guest")

                enemyMessage = {
                    "Action": "GameOver",
                    "Winner": winnerColor
                }
                await enemySocket.send(json.dumps(enemyMessage))
                break

async def main():
    async with websockets.serve(HandlePlayer, "0.0.0.0", 10000):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())