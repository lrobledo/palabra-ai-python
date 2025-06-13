import asyncio
import io
import logging
import wave

import aiofile
from livekit import rtc

logger = logging.getLogger(__name__)


class AudioBufferWriter:
    def __init__(
        self,
        queue: asyncio.Queue[rtc.AudioFrame] | None = None,
        buffer: io.BytesIO | None = None,
        drop_empty_frames: bool = False,
    ):
        self.buffer = buffer or io.BytesIO()
        self.queue = queue or asyncio.Queue()
        self.drop_empty_frames = drop_empty_frames
        self._stop_event = asyncio.Event()
        self._task = None
        self._frame_sample: rtc.AudioFrame | None = None
        self._frames_processed = 0

    async def start(self):
        logger.debug(f"AudioBufferWriter.start() called, _task={self._task}")
        if self._task is None:
            logger.debug("Creating _write task...")
            self._task = asyncio.create_task(self._write())
            logger.debug(f"AudioBufferWriter.start() created task: {self._task}")
            await asyncio.sleep(0.1)
            if self._task.done():
                logger.error(
                    f"Task died immediately! Exception: {self._task.exception()}"
                )
        else:
            logger.warning(
                f"AudioBufferWriter.start() called but task already exists: {self._task}"
            )

    async def stop(self):
        if self._task is not None:
            self._stop_event.set()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.warning("AudioBufferWriter stop cancelled")
            self._task = None

    async def _write(self):
        logger.debug(f"AudioBufferWriter._write() STARTED, queue ID: {id(self.queue)}")

        try:
            while True:
                logger.debug(
                    f"_write loop iteration, stop_event={self._stop_event.is_set()}, frames_processed={self._frames_processed}"
                )

                if self._stop_event.is_set():
                    logger.debug("_write: stop_event is set, breaking")
                    break

                try:
                    logger.debug(
                        f"_write: waiting for frame from queue (size={self.queue.qsize()})"
                    )
                    frame: rtc.AudioFrame | None = await asyncio.wait_for(
                        self.queue.get(), timeout=0.1
                    )
                    logger.debug(f"_write: GOT FRAME! {frame}")
                    self._frames_processed += 1
                except TimeoutError:
                    logger.debug("_write: timeout waiting for frame")
                    continue
                except asyncio.CancelledError:
                    logger.warning("_write: queue.get cancelled")
                    raise

                if frame is None:
                    logger.debug("_write: got None frame, breaking")
                    self.queue.task_done()
                    break

                frame_bytes = frame.data.tobytes()

                if self.drop_empty_frames:
                    if all(byte == 0 for byte in frame_bytes):
                        logger.debug("_write: dropping empty frame")
                        self.queue.task_done()
                        continue

                self.buffer.write(frame_bytes)
                self.queue.task_done()
                logger.debug(
                    f"_write: wrote {len(frame_bytes)} bytes to buffer, total processed: {self._frames_processed}"
                )

                if self._frame_sample is None:
                    self._frame_sample = frame
                    logger.debug(
                        f"_write: saved frame sample: channels={frame.num_channels}, rate={frame.sample_rate}"
                    )

                await asyncio.sleep(0)

        except asyncio.CancelledError:
            logger.warning(f"_write: cancelled after {self._frames_processed} frames")
            raise
        finally:
            logger.debug(
                f"_write: EXITED loop, processed {self._frames_processed} frames"
            )

    def to_wav_bytes(self) -> bytes:
        if self._frame_sample is None:
            logger.error("No frame sample available for WAV conversion")
            return b""

        with io.BytesIO() as wav_file:
            with wave.open(wav_file, "wb") as wav:
                wav.setnchannels(self._frame_sample.num_channels)
                wav.setframerate(self._frame_sample.sample_rate)
                wav.setsampwidth(2)
                wav.writeframes(self.buffer.getvalue())
            return wav_file.getvalue()

    async def write_to_disk(self, file_path: str) -> int:
        try:
            async with aiofile.async_open(file_path, "wb") as f:
                return await f.write(self.to_wav_bytes())
        except asyncio.CancelledError:
            logger.warning("AudioBufferWriter write_to_disk cancelled")
            raise
