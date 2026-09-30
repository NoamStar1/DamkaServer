# pip install websockets || py -m pip install websockets
# pip install psycopg2-binary
# pip install asyncpg || py -m pip install asyncpg
# python "F:\Internet\Projects\Damka\server.py"
# not sleeping: uptimerobot.com

import asyncio
import json
import websockets # online server
import asyncpg # data base (supabase.com)

databaseUrl = "postgresql://postgres.ywiazghmzxtdflwirwrg:damkadatabase8339@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
pool = None
requestPlayers = {}
players = {}
admins = []
playingPlayers = []
waitingPlayers = []

async def isUsernameTaken(username):
    query = '''
        SELECT 1 FROM users WHERE username = $1
        UNION
        SELECT 1 FROM pending_users WHERE username = $1
    '''
    result = await pool.fetchval(query, username)
    return result is not None

async def getPendingUsers():
    try:
        pendingList = await pool.fetch("SELECT username, password FROM pending_users;")
        return pendingList
        
    except Exception:
        return []

async def signUpRequest(username, password):
    try:
        if await isUsernameTaken(username):
            return False

        await pool.execute(
            "INSERT INTO pending_users (username, password) VALUES ($1, $2)",
            username, password
        )
        return True

    except Exception:
        return False

async def SignUp(username, isAccepted, socket):
    try:
        if isAccepted:
            players[username] = socket
            await pool.execute("""
                INSERT INTO users (username, password)
                SELECT username, password
                FROM pending_users
                WHERE username = $1;
            """, username)

        await pool.execute("""
            DELETE FROM pending_users WHERE username = $1;
        """, username)
        return True

    except Exception:
        return False

async def logIn(username, password, socket):
    try:
        user = await pool.fetchrow(
            "SELECT is_admin FROM users WHERE username = $1 AND password = $2", 
            username, password
        )
        
        if user is not None:
            # if player is already playing - disconnect them
            message = { "Action": "Refresh"}
            try: 
                await players[username].send(json.dumps(message))
            except:
                pass
            players[username] = socket
            if user["is_admin"]:
                if socket not in admins:
                    admins.append(socket)
                return "Admin"
            return True
        return False
        
    except Exception:
        return False

async def DeleteUser(username):
    try:
        #               "DELETE 1"
        status = await pool.execute(
            "DELETE FROM users WHERE username = $1;",
            username
        )
        #                ["DELETE", "1"]
        rowsdeleted = int(status.split()[-1])
        if rowsdeleted > 0:
            return True
        return "WrongUsername"

    except Exception:
        return False

async def IsAdmin(username):
    try:
        isAdmin = await pool.fetchval(
            "SELECT is_admin FROM users WHERE username = $1;",
            username
        )
        return isAdmin

    except Exception:
        return None

async def ManageAdmin(username, isAdmin):
    try:
        #               "UPDATE 1"
        status = await pool.execute("""
            UPDATE users
            SET is_admin = $1
            WHERE username = $2;
        """, isAdmin, username)
        #                ["UPDATE", "1"]
        rows_updated = int(status.split()[-1])
        return rows_updated > 0

    except Exception:
        return False

async def GetPoints(username):
    try:
        points = await pool.fetchval(
            "SELECT points FROM users WHERE username = $1;",
            username,
        )
        return points

    except Exception:
        return False

async def UpdatePoints(username, pointsToAdd):
    try:
        await pool.execute(
            "UPDATE users SET points = points + $1 WHERE username = $2;",
            pointsToAdd, username,
        )
        return True

    except Exception:
        return False

async def GetLeaderboard():
    try:
        rows = await pool.fetch('''
            SELECT username, points, equipped_items ->> 'CoinIcon' AS coin_icon, equipped_items ->> 'NameStyle' AS name_style
            FROM users
            ORDER BY points DESC
            LIMIT 100;
        ''')
        leaderboard = []
        for row in rows:
            data = {
                "Username": row["username"],
                "Points": row["points"],
                "CoinIcon": row["coin_icon"],
                "NameStyle": row["name_style"]
            }
            leaderboard.append(data)
        return leaderboard

    except Exception:
        return False

async def GetMatchesHistory(username):
    try:
        history = await pool.fetchval('''
            SELECT matches 
            FROM users
            WHERE username = $1;
        ''', username)

        if history is not None:
            return history
        return False

    except Exception:
        return False

async def GetGlobalHistory():
    try:
        rows = await pool.fetch('''
            SELECT player1_name, player1_eats,
                   player2_name, player2_eats,
                   winner
            FROM global_history
            ORDER BY id DESC
            LIMIT 20;
        ''')
        history = []
        for row in rows:
            matchDict = {
                "Player1Name": row["player1_name"],
                "Player1Eats": row["player1_eats"],
                "Player2Name": row["player2_name"],
                "Player2Eats": row["player2_eats"],
                "Winner": row["winner"]
            }
            history.append(matchDict)
        return history

    except Exception:
        return False

async def AddMatchToHistory(username, eats, result, isOnline, isSingle, myTurn, difficulty, enemyName):
    try:
        if username:
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
                elif difficulty == 3:
                    enemyName = "Medium-AI"
                elif difficulty == 8:
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

            # save last 15 matches
            await pool.execute('''
                UPDATE users
                SET matches = (
                    SELECT COALESCE(jsonb_agg(elem ORDER BY ord), '[]'::jsonb)
                    FROM (
                        SELECT elem, ord
                        FROM jsonb_array_elements(COALESCE(matches, '[]'::jsonb) || $1::jsonb) WITH ORDINALITY AS t(elem, ord)
                        ORDER BY ord DESC
                        LIMIT 15
                    ) sub
                )
                WHERE username = $2;
            ''', newMatch, username)

        # global history update
        if isOnline and myTurn == 0:
            if result == "WIN":
                winnerName = playerName
            elif result == "LOSE":
                winnerName = enemyName
            else:
                winnerName = "DRAW"

            # add a new match to global history
            await pool.execute('''
                INSERT INTO global_history (player1_name, player1_eats, player2_name, player2_eats, winner)
                VALUES ($1, $2, $3, $4, $5);
            ''', playerName, eats[0], enemyName, eats[1], winnerName)

            # limit global history matches to 20
            await pool.execute('''
                DELETE FROM global_history
                WHERE id NOT IN (
                    SELECT id FROM global_history
                    ORDER BY id DESC
                    LIMIT 20
                );
            ''')

            globalHistory = await GetGlobalHistory()
            message = {
                "Action": "UpdateGlobalHistory",
                "History": globalHistory,
            }
            for admin in admins:
                await admin.send(json.dumps(message))
        return True

    except Exception:
        return False

async def BuyItem(username, itemType, itemName, itemPrice):
    try:
        # add the itemName into items data, into the itemType array, if not exist already
        query = '''
            UPDATE users
            SET items = jsonb_set(
                items,
                ARRAY[$1::text],
                (items->$1) || to_jsonb($2::text)
            )
            WHERE username = $3
            AND NOT (items->$1 @> to_jsonb($2::text));
        '''
        result = await pool.execute(query, itemType, itemName, username)
        if result == "UPDATE 1":
            await UpdatePoints(username, -itemPrice)
            return True
        return False
    except Exception:
        return False

async def EquipItem(username, itemType, itemName):
    try:
        query = '''
            UPDATE users
            SET equipped_items = jsonb_set(
                equipped_items,
                ARRAY[$1::text],
                to_jsonb($2::text)
            )
            WHERE username = $3
        '''
        result = await pool.execute(query, itemType, itemName, username)
        
        if result == "UPDATE 1":
            return True
        return False

    except Exception as e:
        return False

async def GetItems(username):
    try:
        row = await pool.fetchrow('''
            SELECT items, equipped_items 
            FROM users 
            WHERE username = $1;
        ''', username)

        items = row['items']
        equipped_items = row['equipped_items']
        return {
            "Owned": items,
            "Equipped": equipped_items
        }

    except Exception as e:
        return False

async def GetAllUsernames():
    try:
        rows = await pool.fetch('SELECT username FROM users;')
        # transform into Array
        usernames = []
        for row in rows:
            usernames.append(row['username'])
        return usernames

    except Exception:
        return []


async def initDatabase():
    global pool
    try:
        pool = await asyncpg.create_pool(databaseUrl, statement_cache_size=0)
        await pool.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username VARCHAR(20) UNIQUE NOT NULL,
                    password VARCHAR(20) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    points INT DEFAULT 0,
                    matches JSONB DEFAULT '[]'::jsonb,
                    items JSONB DEFAULT '{
                        "PieceSkin": ["Basic"],
                        "CoinIcon": ["Bronze"],
                        "NameStyle": ["Basic"],
                        "Background": ["Purple"]
                    }'::jsonb,
                    equipped_items JSONB DEFAULT '{
                        "PieceSkin": "Basic",
                        "CoinIcon": "Bronze",
                        "NameStyle": "Basic",
                        "Background": "Purple"
                    }'::jsonb
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
        print("database running.")
    except Exception as e:
        print(f"Error in initDatabase: {e}")

async def inspectTables():
    try:
        tables = ['users', 'pending_users', 'global_history']

        for table in tables:
            print(f"--- Table: {table} ---")

            columns = await pool.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = $1;
            """, table)
            
            print("Columns:", [col["column_name"] for col in columns])

            rows = await pool.fetch(f"SELECT * FROM {table};")
            
            data = [dict(row) for row in rows]
            print("Data:", data)
            print()

    except Exception as e:
        print(f"Error inspecting database: {e}")

async def resetDatabase():
    try:
        await pool.execute("DROP TABLE IF EXISTS global_history CASCADE;")
        print("Database reset successfully!")
    except Exception as e:
        print(f"Error dropping table: {e}")

async def ResetUserItems(username):
    global pool
    try:
        async with pool.acquire() as conn:
            await conn.execute('''
                UPDATE users 
                SET items = DEFAULT, 
                    equipped_items = DEFAULT 
                WHERE username = $1;
            ''', username)
        print(f"Items reset to default for {username}")
        return True
    except Exception as e:
        print(f"Error in ResetUserItems: {e}")
        return False

#resetDatabase()

# update leaderboard for all players every 60 seconds
async def LeaderboardLoop():
    while True:
        try:
            await asyncio.sleep(60)
            leaderboard = await GetLeaderboard()
            if leaderboard is not False:
                message = {
                    "Action": "UpdateLeaderboard",
                    "Leaderboard": leaderboard,
                }
                await asyncio.gather(
                    *[player.send(json.dumps(message)) for player in players.values()],
                    return_exceptions=True
                )
        except Exception:
            pass

async def HandlePlayer(player):
    try:
        async for message in player:
            data = json.loads(message)
            action = data.get("Action")
            if action == "WaitingPlayer":
                playerUsername = data.get("Username")
                settings = data.get("Settings")
                pieceName = data.get("PieceName")
                nameStyle = data.get("NameStyle")
                playerData = [player, settings, pieceName, nameStyle]
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
                    enemyPiece = enemyData[0][2]
                    enemyNameStyle = enemyData[0][3]
                    waitingPlayers.remove(enemyData)
                    playingPlayers.append([enemy, player, playerUsername, enemyUsername, [0, 0]]) # add the players into game array
                    playerMessage = {
                        "Action": "StartGame",
                        "EnemyName": enemyUsername or "Guest",
                        "EnemyPiece": enemyPiece,
                        "NameStyle": enemyNameStyle,
                        "Turn": 1,
                    }
                    enemyMessage = {
                        "Action": "StartGame",
                        "EnemyName": playerUsername or "Guest",
                        "EnemyPiece": pieceName,
                        "NameStyle": nameStyle,
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
                result = await signUpRequest(username, password)
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
                leaderboard = await GetLeaderboard()
                result = await SignUp(username, isAccepted, socket)
                items = await GetItems(username)
                requestPlayers.pop(username, None) # if not exits, return None and prevent error
                adminMessage = {
                    "Action": "SignUpResult",
                    "Username": username,
                    "IsAccepted": isAccepted,
                    "Result": result
                }
                await player.send(json.dumps(adminMessage))
                allAdminsMessage = {
                    "Action": "RequestReponsed",
                    "Username": username,
                }
                for admin in admins:
                    if admin is not player:
                        await admin.send(json.dumps(allAdminsMessage))
                message = {
                    "Action": "SignUp",
                    "Username": username,
                    "IsAccepted": isAccepted,
                    "Leaderboard": leaderboard,
                    "Items": items,
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
                history = await GetMatchesHistory(username)
                leaderboard = await GetLeaderboard()
                globalHistory = await GetGlobalHistory()
                points = await GetPoints(username)
                items = await GetItems(username)
                pendingUsers = False
                if result == "Admin":
                    pendingUsers = [user[0] for user in await getPendingUsers()] # get all pending usernames in array
                message = {
                    "Action": "LogIn",
                    "Username": username,
                    "Result": result,
                    "Points": points,
                    "Items": items,
                    "Leaderboard": leaderboard,
                    "History": history,
                    "GlobalHistory": globalHistory,
                    "PendingUsers": pendingUsers
                }
                try:
                    await player.send(json.dumps(message))
                except:
                    pass
            elif action == "DeleteUser":
                username = data.get("Username")
                result = await DeleteUser(username)
                adminMessage = {
                    "Action": "DeleteResult",
                    "Username": username,
                    "Result": result
                }
                await player.send(json.dumps(adminMessage))
                message = { "Action": "Refresh"}
                try: 
                    await players[username].send(json.dumps(message))
                except:
                    pass
            elif action == "SearchAdmin":
                username = data.get("Username")
                result = await IsAdmin(username)
                message = {
                    "Action": "SearchAdminResult",
                    "Username": username,
                    "Result": result,
                }
                await player.send(json.dumps(message))
            elif action == "ManageAdmin":
                username = data.get("Username")
                isAdmin = data.get("IsAdmin")
                globalHistory = await GetGlobalHistory()
                pendingUsers = [user[0] for user in await getPendingUsers()] # get all pending usernames in array
                result = await ManageAdmin(username, isAdmin)
                adminMessage = {
                    "Action": "ManageAdminResult",
                    "IsAdmin": isAdmin,
                    "Result": result
                }
                message = {
                    "Action": "UserAdminResult",
                    "IsAdmin": isAdmin,
                    "GlobalHistory": globalHistory,
                    "PendingUsers": pendingUsers,
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
            elif action == "GetUsernames":
                usernames = await GetAllUsernames()
                message = {
                    "Action": "GetUsernamesResult",
                    "Usernames": usernames,
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
                pointsToAdd = data.get("PointsToAdd")
                result = await AddMatchToHistory(username, eats, result, isOnline, isSingle, myTurn, difficulty, enemyName)
                await UpdatePoints(username, pointsToAdd)
                if result:
                    matchesHistory = await GetMatchesHistory(username)
                    if matchesHistory:
                        message = {
                            "Action": "UpdateMatchesHistory",
                            "Username": username,
                            "History": matchesHistory
                        }
                        try:
                            await player.send(json.dumps(message))
                        except:
                            pass
            elif action == "BuyItem":
                username = data.get("Username")
                itemType = data.get("ItemType")
                itemName = data.get("ItemName")
                itemPrice = data.get("ItemPrice")
                result = await BuyItem(username, itemType, itemName, itemPrice)
                message = {
                    "Action": "BuyItemResult",
                    "Username": username,
                    "ItemType": itemType,
                    "ItemName": itemName,
                    "ItemPrice": itemPrice,
                    "Result": result
                }
                await player.send(json.dumps(message))
            elif action == "EquipItem":
                username = data.get("Username")
                itemType = data.get("ItemType")
                itemName = data.get("ItemName")
                result = await EquipItem(username, itemType, itemName)
                message = {
                    "Action": "EquipItemResult",
                    "Username": username,
                    "ItemType": itemType,
                    "ItemName": itemName,
                    "Result": result
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
                try:
                    await enemySocket.send(json.dumps(enemyMessage))
                except:
                    pass
                break


async def main():
    await initDatabase()
    #await inspectTables()
    #await ResetUserItems("NoamNak")
    #await UpdatePoints("Booogi", 10000)
    asyncio.create_task(LeaderboardLoop())
    async with websockets.serve(HandlePlayer, "0.0.0.0", 10000):
        await asyncio.Future()

asyncio.run(main())