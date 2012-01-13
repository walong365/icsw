#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'see'

import functools, contextlib
import threading, Queue
import zmq
import gevent, gevent.event, gevent.coros, gevent.socket
import socket

_log_lock = threading.RLock()
def log(*args):
	with _log_lock:
		for arg in args:
			print arg + '\t',
		print ''

def _make_pair_socks():
	""" sock1 is normal socket, sock2 is gevent socket """
	old_socket = socket._socketobject
	def _accept_handle(accepted_socket, result):
		sock2, addr = accepted_socket.accept()
		result.append(sock2)
	svr_sock = socket.socket()
	svr_sock.bind(('localhost', 0))
	svr_sock.listen(1)
	result = []
	gevent.spawn(_accept_handle, svr_sock, result)
	sock1 = old_socket()
	sock1.connect(svr_sock.getsockname())
	gevent.sleep(0.3)
	svr_sock.close()
	return sock1, result[0]

class ZmqSocketError(Exception):
	pass

def _closed(func):
	@functools.wraps
	def _func(self, *args, **kw):
		if self.closed:
			raise socket.error, 'socket closed'
		return func(self, *args, **kw)
	return _func

class ZmqContext(threading.Thread):
	WU_WAKE = '1'
	WU_LOCK = '2'
	WU_UNLOCK = '3'
	interval = 1
	def __init__(self):
		threading.Thread.__init__(self)
		self._zmq_context = zmq.Context(1)
		self.poller = zmq.Poller()
		self._zmq_sock = None
		self._gevent_sock = None
		self._lock = gevent.event.Event()
		self._lock._count = 0
		self._thlock = threading.RLock()
		self._socks = {}
		self._zmq_callbacks = []
		self.stoped = True

	def start(self):
		self.stoped = False
		self._zmq_sock, self._gevent_sock = _make_pair_socks()
		self._zmq_sock_fileno = self._zmq_sock.fileno()
		self._gevent_task = gevent.spawn(self._gevent_handle)
		self._gevent_handlers = []
		threading.Thread.start(self)

	def stop(self):
		if not self.stoped:
			self.stoped = True

	def run(self):
		"""
		zmq thread，do zmq poll and callbacks
		"""
		self.poller.register(self._zmq_sock, zmq.POLLIN)
		while not self.stoped:
			items = self.poller.poll(self.interval)
			for so, ptype in items:
				if so in self._socks:
					sock = self._socks[so]
					sock._zmq_handle(ptype)
					self._poll_unregister(so, ptype)
				elif so == self._zmq_sock_fileno:
					data = self._zmq_sock.recv(1024)
					if self.WU_LOCK in data:
						self._zmq_sock.send(self.WU_UNLOCK)
						data = ''
						while data != self.WU_UNLOCK:
							data = self._zmq_sock.recv(1)
			with self._thlock:
				callbacks = self._zmq_callbacks
				self._zmq_callbacks = []
			for callback in callbacks:
				waiter, func, args, kw = callback
				try:
					rs = func(*args, **kw)
					if waiter is not None:
						self.reg_gevent_handler(waiter.set, rs)
				except Exception, e:
					if waiter is not None:
						self.reg_gevent_handler(waiter.set_exception, e)

			try:
				self._zmq_sock.send(self.WU_WAKE)
			except socket.error:
				break
		#stop
		self.stoped = True
		for zmq_sock in self._socks.keys():
			zmq_sock.close()

	def _gevent_handle(self):
		"""
		gevent's thread for handle something
		"""
		while True:
			data = self._gevent_sock.recv(1)
			if data == self.WU_UNLOCK:
				self._lock.set()
			else:
				with self._thlock:
					handlers = self._gevent_handlers
					self._gevent_handlers = []
				while handlers:
					handler, args, kw = handlers.pop(0)
					gevent.spawn(handler, *args, **kw)

	def reg_gevent_handler(self, handler, *args, **kw):
		with self._thlock:
			if handler not in self._gevent_handlers:
				self._gevent_handlers.append((handler, args, kw))

	def socket(self, zmq_type):
		"""
		new zmq socket
		"""
		with self.lock():
			zmq_sock = self._zmq_context.socket(zmq_type)
		sock = _ZmqSocket(self, zmq_sock)
		self._socks[zmq_sock] = sock
		return sock

	def wake_up(self):
		"""
		wake up zmq thread from zmq's poll function
		"""
		self._gevent_sock.send(self.WU_WAKE)

	def zmq_call(self, block, func, *args, **kw):
		""" block is a time """
		if block is None:
			with self._thlock:
				self._zmq_callbacks.append((None, func, args, kw))
			return
		block = int(block)
		waiter = gevent.event.AsyncResult()
		key = (waiter, func, args, kw)
		with self._thlock:
			self._zmq_callbacks.append(key)
		self.wake_up()
		try:
			data = waiter.get(timeout=block)
		except:
			with self._thlock:
				if key in self._zmq_callbacks:
					self._zmq_callbacks.remove(key)
			raise


	@contextlib.contextmanager
	def lock(self, timeout=None):
		"""
		make zmq thread wake up from poll and wait for go on, it is ready for modify zmq's property by main thread
		"""
		if threading.currentThread() == self:
			yield
		elif self._lock.is_set():
			yield
		else:
			try:
				if self._lock._count == 0:
					self._gevent_sock.send(self.WU_LOCK)
				self._lock._count += 1
				self._lock.wait(timeout)
				yield
			finally:
				self._lock._count -= 1
				if self._lock._count == 0:
					self._lock.clear()
					self._gevent_sock.send(self.WU_UNLOCK)

	def _poll_register(self, sock, poll_type, timeout=20):
		def _reg(sock, poll_type):
			pre_type = self.poller.sockets[sock] if sock in self.poller.sockets else 0
			self.poller.register(sock, pre_type | poll_type | zmq.POLLERR) 
		if threading.currentThread() == self:
			_reg(sock, poll_type)
		else:
			self.zmq_call(timeout, _reg, sock, poll_type)

	def _poll_unregister(self, sock, zmq_type=None, timeout=20):
		def _unreg(sock, zmq_type=None):
			if sock not in self.poller.sockets:
				return
			if zmq_type is None:
				self.poller.sockets.pop(sock)
			else:
				pre_type = self.poller.sockets[sock]
				if (pre_type & ~zmq_type) & (zmq.POLLIN | zmq.POLLOUT) == 0:
					self.poller.sockets.pop(sock)
				else:
					self.poller.sockets[sock] = (pre_type & ~zmq_type)
		if threading.currentThread() == self:
			_unreg(sock, zmq_type)
		else:
			self.zmq_call(timeout, _unreg, sock, zmq_type)


	def close_sock(self, sock, timeout=20):
		zmq_sock = sock._sock
		self._socks.pop(zmq_sock, None)
		self._poll_unregister(zmq_sock)
		self.zmq_call(timeout, zmq_sock.close)


class _ZmqSocket(object):
	def __init__(self, context, sock):
		if 0:
			self._context = ZmqContext()
		self._context = context
		self._sock = sock
		self.socket_type = sock.socket_type
		self._send_waiter = gevent.event.Event()
		self._send_lock = gevent.coros.Semaphore()
		self._send_data = None
		self._recv_waiter = gevent.event.Event()
		self._recv_lock = gevent.coros.Semaphore()
		self._recv_data = None
		self._lock = gevent.coros.Semaphore()
		self._thlock = threading.RLock()
		self._init()

	def _init(self):
		assert self.socket_type in [zmq.REQ, zmq.REP, zmq.XREQ, zmq.XREP,\
									zmq.SUB, zmq.PUB, zmq.PUSH, zmq.PULL], 'socket type error'
		self._send_vaild = True
		self._recv_vaild = True
		self._send_want_reg = False
		if self.socket_type in [zmq.SUB, zmq.PULL]:
			self._send_vaild = False
		if self.socket_type in [zmq.PUB, zmq.PUSH]:
			self._recv_vaild = False
		if self.socket_type in [zmq.REQ, zmq.XREQ, zmq.PUSH]:
			self._send_want_reg = True

		self.set_use_multipart(self.socket_type in [zmq.XREP])

	def set_use_multipart(self, is_use):
		self._use_multipart = is_use
		if is_use:
			self._sock_send = self._sock.send_multipart
			self._sock_recv = self._sock.recv_multipart
		else:
			self._sock_send = self._sock.send
			self._sock_recv = self._sock.recv

	def close(self):
		with self._lock:
			if not self.closed:
				self._context.close_sock(self)
				self._recv_waiter.set()
				self._send_waiter.set()

	@property
	def closed(self):
		return self._sock.closed

	def bind(self, addr):
		self._context.zmq_call(None, self._sock.bind, addr)

	def setsockopt(self, type, value):
		self._context.zmq_call(None, self._sock.setsockopt, type, value)

	def connect(self, addr):
		self._context.zmq_call(None, self._sock.connect, addr)

	def register(self, zmq_type):
		self._context._poll_register(self._sock, zmq_type)

	def unregister(self, zmq_type):
		self._context._poll_unregister(self._sock, zmq_type)

	def recv(self, timeout=None):
		assert self._recv_vaild, 'recv unvaild'
		with self._recv_lock:
			self.register(zmq.POLLIN)
			try:
				self._recv_waiter.wait(timeout=timeout)
				data = self._recv_data
			finally:
				self._recv_waiter.clear()
				self._recv_data = None

		return data

	def send(self, data, timeout=None):
		assert self._send_vaild and data is not None, 'send unvaild'
		if not self._send_want_reg:
			self._sock_send(data)
		else:
			with self._send_lock:
				self._send_data = data
				self.register(zmq.POLLOUT)
				try:
					self._send_waiter.wait(timeout=timeout)
				finally:
					self._send_data = None
					self._send_waiter.clear()

	def _gevent_handle_recv(self, data):
		self._recv_data = data
		self._recv_waiter.set()

	def _gevent_handle_send(self):
		self._send_waiter.set()

	def _zmq_handle(self, type):
		if type & zmq.POLLERR == zmq.POLLERR:
			self._context._poll_unregister(self)
			self._sock.close()
			self._context.reg_gevent_handler(self.close)
			return
		if type & zmq.POLLIN == zmq.POLLIN:
			data = self._sock_recv()
#			log('zmq:POLLIN:%s' % data)
			self._context.reg_gevent_handler(self._gevent_handle_recv, data)
		if type & zmq.POLLOUT == zmq.POLLOUT:
			data = self._send_data
#			log('zmq:POLLOUT:%s' % data)
			self._sock.send(data)
			self._context.reg_gevent_handler(self._gevent_handle_send)


def testSUB_PUB(ct, waiter):
	def _sub_handle(name, ports):
		sock = ct.socket(zmq.SUB)
		for port in ports:
			sock.connect('tcp://127.0.0.1:%s' % port)
		sock.setsockopt(zmq.SUBSCRIBE, '')
		count = 0
		while 1:
			data = sock.recv()
			count += 1
			log('<%s> - %s-%d' % (name, data, count))

	def _pub_handle(name, port):
		sock = ct.socket(zmq.PUB)
		sock.bind('tcp://127.0.0.1:%s' % port)
		count = 0
		gevent.sleep(3)
		while count < 10:
			count += 1
			sock.send('<%s>abc-%d' % (name, count))
			gevent.sleep(0.01)
	ports = [12345, 12346, 12347]
	tasks = []
	for index, port in enumerate(ports):
		task = gevent.spawn(_pub_handle, 'pub-%d'%index, port)
		tasks.append(task)
	for i in range(2):
		task = gevent.spawn(_sub_handle, 'sub-%d'%i, ports)

	gevent.joinall(tasks)
	gevent.sleep(3)
	waiter.set()

def testREQ_REP(ct, waiter):
	def _req_handle(name, count, ports):
		sock = ct.socket(zmq.REQ)
		for port in ports:
			sock.connect('tcp://127.0.0.1:%s' % port)
		try:
			while count:
				count -= 1
				if count == 0:
					timeout = 1
					sock.send('%s - timeout' % name)
				else:
					timeout = 2
					sock.send(name)
				log('%s recv' % name)
				data = sock.recv(timeout=timeout)
				msg = 'ok' if data == name else '%s is not "%s"' % (data, name)
				log('%s req: %s'% (name, msg))
#				gevent.sleep(0.2)
		except gevent.Timeout:
			log('%s timeout success' % name)
		finally:
			sock.close()
		log('%s complete' % name)

	def _rep_handle(port):
		sock = ct.socket(zmq.REP)
		sock.bind('tcp://0.0.0.0:%s' % port)
		while 1:
			data = sock.recv()
			log('<rep:%s>%s' % (port, data))
#			if 'timeout' in data:
#				break
			sock.send(data)
		sock.close()
	count = 10
	reqs = []
#	ports = [12345]
	ports = [12345, 12346, 12347]
	for port in ports:
		gevent.spawn(_rep_handle, port)
	for i in range(2):
		task = gevent.spawn(_req_handle, 'req%d'%(i+1), count, ports)
		reqs.append(task)
	gevent.joinall(reqs)
	waiter.set()

def testXREQ_XREP(ct, waiter):
	def _req_handle(name, count, ports):
		sock = ct.socket(zmq.XREQ)
		for port in ports:
			sock.connect('tcp://127.0.0.1:%s' % port)
		try:
			while count:
				count -= 1
				if count == 0:
					timeout = 1
					sock.send('%s - timeout' % name)
				else:
					timeout = 2
					sock.send(name)
				log('%s recv' % name)
				data = sock.recv(timeout=timeout)
				msg = 'ok' if data == name else '%s is not "%s"' % (data, name)
				log('%s req: %s'% (name, msg))
				#gevent.sleep(0.01)
		except gevent.Timeout:
			log('%s timeout success' % name)
		finally:
			sock.close()
		log('%s complete' % name)

	def _rep_handle(port):
		sock = ct.socket(zmq.XREP)
		sock.bind('tcp://0.0.0.0:%s' % port)
		while 1:
			id, data = sock.recv()
			log('<rep:%s>%s' % (port, data))
#			if 'timeout' in data:
#				break
			sock.send([id, data])
		sock.close()
	count = 10
	reqs = []
#	ports = [12345]
	ports = [12345, 12346, 12347]
	for port in ports:
		gevent.spawn(_rep_handle, port)
	for i in range(2):
		task = gevent.spawn(_req_handle, 'req%d'%(i+1), count, ports)
		reqs.append(task)
	gevent.joinall(reqs)
	waiter.set()

def testPUSH_PULL(ct, waiter):
	def _push_handle(name, port, count):
		sock = ct.socket(zmq.PUSH)
		sock.bind('tcp://0.0.0.0:%d' % port)
		while count > 0:
			log('<push>%s send:%s' % (name, count))
			sock.send('%s-%d' % (name, count))
			count -= 1

	def _pull_handle(name, ports):
		sock = ct.socket(zmq.PULL)
		for port in ports:
			sock.connect('tcp://127.0.0.1:%d' % port)
		while 1:
			log('<pull>%s recving' % name)
			data = sock.recv()
			log('<pull>%s recv:%s' % (name, data))
			gevent.sleep(1)
#			break
		sock.close()

	ports = [12345, 12346, 12347]
	#ports = [12345]
	tasks = []
	count = 5
	for index, port in enumerate(ports):
		task = gevent.spawn(_push_handle, 'push-%d' %index, port, count)
		tasks.append(task)
	for i in range(1):
		gevent.spawn(_pull_handle, 'pull-%d' % i, ports)
		
	gevent.joinall(tasks)
	gevent.sleep(5)
	waiter.set()


def start_test(func):
	from gevent import monkey; monkey.patch_all()
	ct = ZmqContext()
	ct.start()
	waiter = gevent.event.Event()
	try:
		log('*' * 5, 'test:%s' % func, '*' * 5)
		func(ct, waiter)
		waiter.wait()
	except KeyboardInterrupt:
		pass
	finally:
		ct.stop()

if __name__ == '__main__':
	start_test(testSUB_PUB)
#	start_test(testREQ_REP)
#	start_test(testXREQ_XREP)
#	start_test(testPUSH_PULL)
