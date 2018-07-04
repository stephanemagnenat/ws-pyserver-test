#!/usr/bin/env python3.6

# inspired from https://websockets.readthedocs.io/en/stable/intro.html
# WS server example

import asyncio
import json
import logging
import websockets

logging.basicConfig()

STATE = {'value': 0}

USERS = {}


def state_event():
	return json.dumps({'type': 'state', **STATE})

def message_user_new(name):
	return json.dumps({'type': 'user_new', 'name': name})

def message_user_part(name):
	return json.dumps({'type': 'user_part', 'name': name})


async def notify_state():
	print(f"- new state {STATE['value']}")
	if USERS:       # asyncio.wait doesn't accept an empty list
		message = state_event()
		await asyncio.wait([user.send(message) for user in USERS])

async def notify_user_new(name):
	if USERS:       # asyncio.wait doesn't accept an empty list
		message = message_user_new(name)
		await asyncio.wait([user.send(message) for user in USERS])

async def notify_user_part(name):
	if USERS:       # asyncio.wait doesn't accept an empty list
		message = message_user_part(name)
		await asyncio.wait([user.send(message) for user in USERS])


async def register(websocket):
	name = await websocket.recv()
	USERS[websocket] = name
	print(f"> {name} connected")
	await notify_user_new(name)

async def unregister(websocket):
	name = USERS[websocket]
	del USERS[websocket]
	print(f"> {name} disconnected")
	await notify_user_part(name)


async def counter(websocket, path):
	# register(websocket) sends user_event() to websocket
	await register(websocket)
	try:
		await websocket.send(state_event())
		async for message in websocket:
			data = json.loads(message)
			if data['action'] == 'minus':
				STATE['value'] -= 1
				await notify_state()
			elif data['action'] == 'plus':
				STATE['value'] += 1
				await notify_state()
			else:
				logging.error("unsupported event: {}", data)
	finally:
		await unregister(websocket)

asyncio.get_event_loop().run_until_complete(websockets.serve(counter, 'localhost', 6789))
asyncio.get_event_loop().run_forever()
