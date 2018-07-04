#!/usr/bin/env python3.6

# inspired from https://websockets.readthedocs.io/en/stable/intro.html
# WS server example

import asyncio
import json
import logging
import websockets
import time
import numpy as np

# enable logging

logging.basicConfig(level=logging.DEBUG)

# game classes

class Player:
	def __init__(self, name):
		self.name = name
		self.pos = np.ones(2) * WORLD_SIZE / 2
		self.hits = 0
		self.speed = np.zeros(2)
		self.last_fire_time = time.time()

	def move(self, speed):
		self.speed = np.array(speed)

	def step(self, dt):
		# return true if clipping occurs
		self.pos += self.speed * dt
		new_pos = np.clip(self.pos, 0, WORLD_SIZE)
		if not np.array_equal(new_pos, self.pos):
			self.pos = new_pos
			self.speed[:] = [0,0]
			return True
		return False

# game state

players = {}

# game constants

UPDATE_PERIOD = 0.05

WORLD_SIZE = 200

TIME_BETWEEN_FIRE = 1

DIST_TO_HIT = 20

# network processing methods

## message building

def message_player_new(player):
	return json.dumps({
		'type': 'player_new',
		'name': player.name,
		'pos': player.pos.tolist(),
		'speed': player.speed.tolist(),
		'hits': player.hits
	})

def message_player_status(player):
	return json.dumps({
		'type': 'player_state',
		'name': player.name,
		'pos': player.pos.tolist(),
		'speed': player.speed.tolist(),
		'hits': player.hits
	})

def message_player_part(player):
	return json.dumps({'type': 'player_part', 'name': player.name})

## notification helper methods

async def notify_players(source_player, messager_builder_function):
	if players:       # asyncio.wait doesn't accept an empty list
		message = messager_builder_function(source_player)
		await asyncio.wait([websocket.send(message) for websocket in players])

## network processing callbacks

async def register(websocket):
	# receive the name from this player
	name = await websocket.recv()
	player = Player(name)
	# send the current state to this player
	for other_websocket, other_player in players.items():
		await websocket.send(message_player_new(other_player))
	# add to the list of players
	players[websocket] = player
	# tell all players about this new one
	await notify_players(player, message_player_new)
	# print and return
	print(f"> {name} connected")
	return player

async def unregister(websocket):
	# remove from the list of players
	player = players[websocket]
	del players[websocket]
	# tell others players about this disconnection
	await notify_players(player, message_player_part)
	print(f"> {player.name} disconnected")

## client processing code

async def process_client(websocket, path):
	# register(websocket) sends user_event() to websocket
	player = await register(websocket)
	try:
		# process messages from this player
		async for message in websocket:
			data = json.loads(message)
			if data['action'] == 'move':
				# set the speed of the player
				player.move(data['speed'])
				await notify_players(player, message_player_status)
			elif data['action'] == 'fire':
				cur_time = time.time()
				if cur_time - player.last_fire_time < TIME_BETWEEN_FIRE:
					# we are not allowed to fire
					continue
				# see if any other player has been hit
				did_hit = False
				for other_websocket, other_player in players.items():
					if other_player == player:
						continue
					# if we hit the other
					if np.linalg.norm(other_player.pos - player.pos) < DIST_TO_HIT:
						did_hit = True
						# increase our hits
						player.hits += 1
						# disable fire for other
						other_player.last_fire_time = cur_time
				# if we did hit, update the client
				if did_hit:
					await notify_players(player, message_player_status)
				player.last_fire_time = cur_time
			else:
				logging.error("unsupported event: {}", data)
	finally:
		await unregister(websocket)

## server-side state update

async def run_state():
	last_time = time.time()
	while True:
		cur_time = time.time()
		for websocket, player in players.items():
			#print (player.name)
			#print (player.pos)
			#print (player.speed)
			if player.step(cur_time - last_time):
				await notify_players(player, message_player_status)
		last_time = cur_time
		await asyncio.sleep(UPDATE_PERIOD)

## main code

loop = asyncio.get_event_loop()
loop.run_until_complete(websockets.serve(process_client, '', 6789))
loop.run_until_complete(run_state())
