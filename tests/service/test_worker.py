import fakeredis

from manim_skill.service import worker as worker_mod


def test_worker_module_exposes_main():
    assert callable(worker_mod.main)


def test_build_worker_constructs_an_rq_worker():
    # _build_worker wires an RQ Worker onto the manim-skill queue
    # without entering the blocking .work() loop.
    redis_conn = fakeredis.FakeRedis()
    worker = worker_mod._build_worker(redis_conn)
    assert "manim-skill" in worker.queue_names()
