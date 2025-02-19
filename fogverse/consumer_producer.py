import asyncio
import os
import queue
import socket
import sys
import uuid

from aiokafka import (
    AIOKafkaConsumer as _AIOKafkaConsumer,
    AIOKafkaProducer as _AIOKafkaProducer
)
from .base import AbstractConsumer, AbstractProducer, AbstractProcessor
from confluent_kafka import Consumer, Message, Producer
from fogverse.logger import FogVerseLogging, get_logger
from fogverse.utils import get_config
from threading import Event

class AIOKafkaConsumer(AbstractConsumer):
    def __init__(self, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self._topic_pattern = get_config('TOPIC_PATTERN', self)

        self._consumer_topic = get_config('CONSUMER_TOPIC', self, [])
        if isinstance(self._consumer_topic, str):
            self._consumer_topic = self._consumer_topic.split(',')

        self._consumer_servers = get_config('CONSUMER_SERVERS', self,
                                             'localhost')
        self.consumer_conf = getattr(self, 'consumer_conf', {})
        self.consumer_conf = {
            'loop': self._loop,
            'bootstrap_servers': self._consumer_servers,
            'group_id': get_config('GROUP_ID', self, str(uuid.uuid4())),
            'client_id': get_config('CLIENT_ID', self, socket.gethostname()),
            **self.consumer_conf}
        if self._consumer_topic:
            self.consumer = _AIOKafkaConsumer(*self._consumer_topic,
                                            **self.consumer_conf)
        else:
            self.consumer = _AIOKafkaConsumer(**self.consumer_conf)
        self.seeking_end = None

    async def start_consumer(self):
        logger = getattr(self, '_log', None)
        if logger is not None and isinstance(logger, FogVerseLogging):
            logger.std_log('Topic: %s', self._consumer_topic)
            logger.std_log('Config: %s', self.consumer_conf)
        await self.consumer.start()
        if self._topic_pattern:
            self.consumer.subscribe(pattern=self._topic_pattern)
        await asyncio.sleep(5) # wait until assigned to partition
        if getattr(self, 'read_last', True):
            await self.consumer.seek_to_end()

    async def receive(self):
        if getattr(self, 'always_read_last', False):
            if asyncio.isfuture(self.seeking_end):
                await self.seeking_end
            self.seeking_end = \
                asyncio.ensure_future(self.consumer.seek_to_end())
            if getattr(self, 'always_await_seek_end', False):
                await self.seeking_end
                self.seeking_end = None
        return await self.consumer.getone()

    async def close_consumer(self):
        await self.consumer.stop()
        logger = getattr(self, '_log', None)
        if isinstance(logger, FogVerseLogging):
            logger.std_log('Consumer has closed.')

class ConfluentKafkaConsumer:
    def __init__(self):
        self._topic_pattern = get_config('TOPIC_PATTERN', self)
        self.log = get_logger(name=self.__class__.__name__)
        self._group_id  = get_config('GROUP_ID', self, str(uuid.uuid4()))
        self._poll_time = get_config('POLL_TIME', self, 1.0)
        self._batch_size = get_config('BATCH_SIZE', self, 1)

        self._consumer_servers = get_config('CONSUMER_SERVERS', self,
                                             'localhost')
        self._consumer_topic = get_config('CONSUMER_TOPIC', self)
        self._consumer_id = get_config('CONSUMER_ID', self, str(uuid.uuid4()))
        self.consumer_auto_scaler = getattr(self, 'consumer_auto_scaler', None)

        self.consumer_conf = getattr(self, 'consumer_conf', {})
        self.consumer = Consumer({
            'bootstrap.servers': self._consumer_servers,
            'group.id': self._group_id,
            'client.id':  get_config('CLIENT_ID', self, socket.gethostname()),
            **self.consumer_conf
        })


    def _add_to_queue(self, consumed_messages, queue: queue.Queue):
        if  not consumed_messages:
            return queue.put(None)
        for consumed_message in consumed_messages:
            queue.put(consumed_message)

    def start_confluent_consumer(self, stop_event: Event, queue:  queue.Queue):
        if self.consumer_auto_scaler is not None:
            self.consumed_messages = self.consumer_auto_scaler.start_with_distributed_lock(
                self.consumer,
                self._consumer_topic,
                self._group_id,
                self._consumer_id
            )
        else:
            self.consumer.subscribe([self._consumer_topic])
        self._add_to_queue(queue)

        try:
            while not stop_event.is_set():
                messages: list[Message] = self.consumer.consume(self._batch_size, self._poll_time)
                for message in messages:
                    queue.put(message)
        except Exception as e:
            self.log.error(e)

class AIOKafkaProducer(AbstractProducer):
    def __init__(self, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self.producer_topic = get_config('PRODUCER_TOPIC', self)
        self._producer_servers = get_config('PRODUCER_SERVERS', self)
        self._producer_conf = getattr(self, 'producer_conf', {})
        self._producer_conf = {
            'loop': self._loop,
            'bootstrap_servers': self._producer_servers,
            'client_id': get_config('CLIENT_ID', self, socket.gethostname()),
            **self._producer_conf}
        self.producer = _AIOKafkaProducer(**self._producer_conf)

    async def start_producer(self):
        logger = getattr(self, '_log', None)
        if isinstance(logger, FogVerseLogging):
            logger.std_log('Config: %s', self._producer_conf)
            if getattr(self, 'producer_topic', None) is not None:
                logger.std_log('Topic: %s', self.producer_topic)
        await self.producer.start()

    async def _send(self, data, *args, topic=None, headers=None, key=None,
                    **kwargs):
        if topic is None: raise ValueError('Topic should not be None.')
        return await self.producer.send(topic,
                                        *args,
                                        value=data,
                                        key=key,
                                        headers=headers,
                                        **kwargs)

    async def close_producer(self):
        await self.producer.stop()
        logger = getattr(self, '_log', None)
        if isinstance(logger, FogVerseLogging):
            logger.std_log('Producer has closed.')

class ConfluentKafkaProducer:
    def __init__(self, callback = False):
        self._callback = callback
        self._batch_size = get_config('BATCH_SIZE', self, 1)
        self.processor: AbstractProcessor = getattr(self, 'processor', None)
        self.log = get_logger(name=self.__class__.__name__)

        self.producer_queue = queue
        self.producer_topic = get_config('PRODUCER_TOPIC', self)
        self._producer_servers = get_config('PRODUCER_SERVERS', self)
        self.producer_callback = getattr(self, 'producer_callback', None)
        self.producer_on_complete = getattr(self, 'producer_on_complete', None)

        self._producer_conf = getattr(self, 'producer_conf', {})
        self.producer = Producer({
            'bootstrap.servers': self._producer_servers,
            'client.id':  get_config('CLIENT_ID', self, socket.gethostname()),
            **self._producer_conf
        })

    def start_producer(self, queue: queue.Queue, stop_event: Event):
        try:
            message_batch: list[Message] = []
            while not stop_event.is_set():
                message: Message = queue.get()
                if self.producer_callback and not self._callback:
                    self._callback = True
                    self.producer_callback(lambda x, y:
                                           self.producer.produce(topic=x, value=y))

                if message is None:
                    continue
                elif message.error():
                    self.log.error(message.error())

                message_batch.append(message)

                if len(message_batch) < self._batch_size:
                    continue
                else:
                    total_messages = len(message_batch)
                    results: list[bytes] = self.processor.process(message_batch)
                    for result in results:
                        self.producer.produce(topic=self.topic, value=result)
                        self.producer.flush()
                    queue.task_done()
                    message_batch.clear()
                    self.producer_on_complete(
                        self.topic,
                        total_messages,
                        lambda x, y: self.producer.produce(
                            topic=x,
                            value=y
                        )
                    )
        except Exception as e:
            self.log.error(e)

def _get_cv_video_capture(device=0):
    import cv2
    return cv2.VideoCapture(device)

class OpenCVConsumer(AbstractConsumer):
    def __init__(self, loop=None, executor=None):
        self._device = get_config('DEVICE', self, 0)
        self.consumer = getattr(self, 'consumer', None) or \
                            _get_cv_video_capture(self._device)
        self._loop = loop or asyncio.get_event_loop()
        self._executor = executor

    def close_consumer(self):
        self.consumer.release()
        logger = getattr(self, '_log', None)
        if isinstance(logger, FogVerseLogging):
            logger.std_log('OpenCVConsumer has closed.')

    async def receive_error(self, frame=None):
        logger = getattr(self, '_log', None)
        if isinstance(logger, FogVerseLogging):
            logger.std_log('Done OpenCVConsumer consuming the camera.')
        sys.exit(0)

    async def receive(self):
        success, frame = self.consumer.read()
        if not success:
            return await self.receive_error(frame)
        return frame
