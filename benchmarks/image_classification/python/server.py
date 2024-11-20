# MIT License

# Modification 2023 HyScale lab and vSwarm team
# Copyright (c) MLPerf inference benchmark team

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import array
import collections
import json
import os
import sys
import threading
import time
from queue import Queue

from backend_tf import BackendTensorflow

import mlperf_loadgen as lg
import numpy as np

import dataset
import imagenet

from proto.image_classification import image_classification_pb2
import image_classification_pb2_grpc
import grpc
from concurrent import futures
import logging

NANO_SEC = 1e9
MILLI_SEC = 1000

SUPPORTED_DATASETS = {
    "imagenet":
        (imagenet.Imagenet, dataset.pre_process_vgg, dataset.PostProcessCommon(offset=-1),
         {"image_size": [224, 224, 3]}),
}

# pre-defined command line options so simplify things. They are used as defaults and can be
# overwritten from command line

SUPPORTED_PROFILES = {
    "defaults": {
        "dataset": "imagenet",
        "backend": "tensorflow",
        "cache": 0,
        "max-batchsize": 32,
    },
    "resnet50-tf": {
        "inputs": "input_tensor:0",
        "outputs": "ArgMax:0",
        "dataset": "imagenet",
        "backend": "tensorflow",
        "model-name": "resnet50",
    },
}

SCENARIO_MAP = {
    "SingleStream": lg.TestScenario.SingleStream,
    "MultiStream": lg.TestScenario.MultiStream,
    "Server": lg.TestScenario.Server,
    "Offline": lg.TestScenario.Offline,
}

last_timeing = []


def get_args():
    """Parse commandline."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="imagenet", choices=SUPPORTED_DATASETS.keys(), help="dataset")
    parser.add_argument("--dataset-list", help="path to the dataset list")
    parser.add_argument("--dataset-path", default="/app/data_imagenet", help="path to the dataset")
    parser.add_argument("--profile", default="resnet50-tf", help="standard profiles")
    parser.add_argument("--scenario", default="Offline",
                        help="mlperf benchmark scenario, one of " + str(list(SCENARIO_MAP.keys())))
    parser.add_argument("--max-batchsize", type=int, help="max batch size in a single inference")
    parser.add_argument("--model", default="/app/models/resnet50_v1.pb", help="model file")
    parser.add_argument("--output", default="/app/output", help="test results")
    parser.add_argument("--threads", default=os.cpu_count(), type=int, help="threads")
    parser.add_argument("--qps", type=int, help="target qps")
    parser.add_argument("--cache", type=int, default=0, help="use cache")
    parser.add_argument("--cache_dir", type=str, default=None, help="dir path for caching")
    parser.add_argument("--preprocessed_dir", type=str, default=None, help="dir path for storing preprocessed images (overrides cache_dir)")
    parser.add_argument("--accuracy", action="store_true", help="enable accuracy pass")
    parser.add_argument("--find-peak-performance", action="store_true", help="enable finding peak performance pass")
    parser.add_argument("--debug", action="store_true", help="debug, turn traces on")
    parser.add_argument("--backend", help="runtime to use")
    parser.add_argument("--inputs", help="model inputs")
    parser.add_argument("--outputs", help="model outputs")
    parser.add_argument("--model-name", help="name of the mlperf model, ie. resnet50")
    parser.add_argument("--use_preprocessed_dataset", action="store_true", help="use preprocessed dataset instead of the original")

    # file to use mlperf rules compliant parameters
    parser.add_argument("--mlperf_conf", default="/tmp/python/configs/user.conf", help="mlperf rules config")
    # file for user LoadGen settings such as target QPS
    parser.add_argument("--user_conf", default="/tmp/python/configs/user.conf", help="user config for user LoadGen settings such as target QPS")
    # file for LoadGen audit settings
    parser.add_argument("--audit_conf", default="audit.config", help="config for LoadGen audit settings")

    # below will override mlperf rules compliant settings
    parser.add_argument("--time", type=int, help="time to scan in seconds")
    parser.add_argument("--count", type=int, help="dataset items to use")
    parser.add_argument("--performance-sample-count", type=int, help="performance sample count")
    parser.add_argument("--max-latency", type=float, help="mlperf max latency in pct tile")
    parser.add_argument("--samples-per-query", default=8, type=int, help="mlperf multi-stream samples per query")
    
    parser.add_argument("--addr", dest="addr", default="0.0.0.0", help="IP address")
    parser.add_argument("--port", dest="port", default="50051", help="serve port")

    args = parser.parse_args()

    defaults = SUPPORTED_PROFILES["defaults"]

    if args.profile:
        profile = SUPPORTED_PROFILES[args.profile]
        defaults.update(profile)
    for k, v in defaults.items():
        kc = k.replace("-", "_")
        if getattr(args, kc) is None:
            setattr(args, kc, v)

    if args.scenario not in SCENARIO_MAP:
        parser.error("valid scanarios:" + str(list(SCENARIO_MAP.keys())))
    return args


class Item:
    """An item that we queue for processing by the thread pool."""

    def __init__(self, query_id, content_id, img, label=None):
        self.query_id = query_id
        self.content_id = content_id
        self.img = img
        self.label = label
        self.start = time.time()


class RunnerBase:
    def __init__(self, model, ds, threads, post_proc=None, max_batchsize=128):
        self.take_accuracy = False
        self.ds = ds
        self.model = model
        self.post_process = post_proc
        self.threads = threads
        self.take_accuracy = False
        self.max_batchsize = max_batchsize
        self.result_timing = []

    def handle_tasks(self, tasks_queue):
        pass

    def start_run(self, result_dict, take_accuracy):
        self.result_dict = result_dict
        self.result_timing = []
        self.take_accuracy = take_accuracy
        self.post_process.start()

    def run_one_item(self, qitem):
        # run the prediction
        processed_results = []
        try:
            results = self.model.predict({self.model.inputs[0]: qitem.img})
            processed_results = self.post_process(results, qitem.content_id, qitem.label, self.result_dict)
            if self.take_accuracy:
                self.post_process.add_results(processed_results)
            self.result_timing.append(time.time() - qitem.start)
        except Exception as ex:  # pylint: disable=broad-except
            src = [self.ds.get_item_loc(i) for i in qitem.content_id]
            # since post_process will not run, fake empty responses
            processed_results = [[]] * len(qitem.query_id)
        finally:
            response_array_refs = []
            response = []
            for idx, query_id in enumerate(qitem.query_id):
                response_array = array.array("B", np.array(processed_results[idx], np.float32).tobytes())
                response_array_refs.append(response_array)
                bi = response_array.buffer_info()
                response.append(lg.QuerySampleResponse(query_id, bi[0], bi[1]))
            lg.QuerySamplesComplete(response)

    def enqueue(self, query_samples):
        idx = [q.index for q in query_samples]
        query_id = [q.id for q in query_samples]
        if len(query_samples) < self.max_batchsize:
            data, label = self.ds.get_samples(idx)
            self.run_one_item(Item(query_id, idx, data, label))
        else:
            bs = self.max_batchsize
            for i in range(0, len(idx), bs):
                data, label = self.ds.get_samples(idx[i:i+bs])
                self.run_one_item(Item(query_id[i:i+bs], idx[i:i+bs], data, label))

    def finish(self):
        pass


class QueueRunner(RunnerBase):
    def __init__(self, model, ds, threads, post_proc=None, max_batchsize=128):
        super().__init__(model, ds, threads, post_proc, max_batchsize)
        self.tasks = Queue(maxsize=threads * 4)
        self.workers = []
        self.result_dict = {}

        for _ in range(self.threads):
            worker = threading.Thread(target=self.handle_tasks, args=(self.tasks,))
            worker.daemon = True
            self.workers.append(worker)
            worker.start()

    def handle_tasks(self, tasks_queue):
        """Worker thread."""
        while True:
            qitem = tasks_queue.get()
            if qitem is None:
                # None in the queue indicates the parent want us to exit
                tasks_queue.task_done()
                break
            self.run_one_item(qitem)
            tasks_queue.task_done()

    def enqueue(self, query_samples):
        idx = [q.index for q in query_samples]
        query_id = [q.id for q in query_samples]
        if len(query_samples) < self.max_batchsize:
            data, label = self.ds.get_samples(idx)
            self.tasks.put(Item(query_id, idx, data, label))
        else:
            bs = self.max_batchsize
            for i in range(0, len(idx), bs):
                ie = i + bs
                data, label = self.ds.get_samples(idx[i:ie])
                self.tasks.put(Item(query_id[i:ie], idx[i:ie], data, label))

    def finish(self):
        # exit all threads
        for _ in self.workers:
            self.tasks.put(None)
        for worker in self.workers:
            worker.join()


class Greeter(image_classification_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        token = request.name
        msg = do_image_classification_inference()
        logging.info("Reply message: ", msg)
        return image_classification_pb2.HelloReply(message=msg)

def serve():
    args = get_args()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    image_classification_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    address = (args.addr + ":" + args.port)
    server.add_insecure_port(address)
    logging.info("Start image_classification-python server. Addr: " + address)
    server.start()
    server.wait_for_termination()

def add_results(final_results, name, result_dict, result_list, took, show_accuracy=False):
    percentiles = [50., 80., 90., 95., 99., 99.9]
    buckets = np.percentile(result_list, percentiles).tolist()
    buckets_str = ",".join(["{}:{:.4f}".format(p, b) for p, b in zip(percentiles, buckets)])

    if result_dict["total"] == 0:
        result_dict["total"] = len(result_list)

    # this is what we record for each run
    result = {
        "took": took,
        "mean": np.mean(result_list),
        "percentiles": {str(k): v for k, v in zip(percentiles, buckets)},
        "qps": len(result_list) / took,
        "count": len(result_list),
        "good_items": result_dict["good"],
        "total_items": result_dict["total"],
    }
    acc_str = ""
    if show_accuracy:
        result["accuracy"] = 100. * result_dict["good"] / result_dict["total"]
        acc_str = ", acc={:.3f}%".format(result["accuracy"])
        if "mAP" in result_dict:
            result["mAP"] = 100. * result_dict["mAP"]
            acc_str += ", mAP={:.3f}%".format(result["mAP"])

    # add the result to the result dict
    final_results[name] = result

    # to stdout
    result = "{} qps={:.2f}, mean={:.4f}, time={:.3f}{}, queries={}, tiles={}".format(
        name, result["qps"], result["mean"], took, acc_str,
        len(result_list), buckets_str)
    logging.info(result)
    return result


def do_image_classification_inference():
    global last_timeing
    args = get_args()

    backend = BackendTensorflow()
    image_format = backend.image_format()

    # --count applies to accuracy mode only and can be used to limit the number of images
    # for testing.
    count_override = False
    count = args.count
    if count:
        count_override = True

    # dataset to use
    wanted_dataset, pre_proc, post_proc, kwargs = SUPPORTED_DATASETS["imagenet"]
    if args.use_preprocessed_dataset:
        pre_proc=None
    ds = wanted_dataset(data_path=args.dataset_path,
                        image_list=args.dataset_list,
                        name=args.dataset,
                        image_format=image_format,
                        pre_process=pre_proc,
                        use_cache=args.cache,
                        count=count,
                        cache_dir=args.cache_dir,
                        preprocessed_dir=args.preprocessed_dir,
                        threads=args.threads,
                        **kwargs)
    # load model to backend
    model = backend.load(args.model, inputs=['input_tensor:0'], outputs=['ArgMax:0'])
    final_results = {
        "runtime": model.name(),
        "version": model.version(),
        "time": int(time.time()),
        "args": vars(args),
        "cmdline": str(args),
    }

    mlperf_conf = os.path.abspath(args.mlperf_conf)
    user_conf = os.path.abspath(args.user_conf)
    audit_config = os.path.abspath(args.audit_conf)

    if args.output:
        output_dir = os.path.abspath(args.output)
        os.makedirs(output_dir, exist_ok=True)
        os.chdir(output_dir)

    #
    # make one pass over the dataset to validate accuracy
    #
    count = ds.get_item_count()

    # warmup
    ds.load_query_samples([0])
    for _ in range(5):
        img, _ = ds.get_samples([0])
        _ = backend.predict({backend.inputs[0]: img})
    ds.unload_query_samples(None)

    scenario = SCENARIO_MAP[args.scenario]
    runner_map = {
        lg.TestScenario.SingleStream: RunnerBase,
        lg.TestScenario.MultiStream: QueueRunner,
        lg.TestScenario.Server: QueueRunner,
        lg.TestScenario.Offline: QueueRunner
    }
    runner = runner_map[scenario](model, ds, args.threads, post_proc=post_proc, max_batchsize=args.max_batchsize)

    def issue_queries(query_samples):
        runner.enqueue(query_samples)

    def flush_queries():
        pass

    log_output_settings = lg.LogOutputSettings()
    log_output_settings.outdir = output_dir
    log_output_settings.copy_summary_to_stdout = False
    log_settings = lg.LogSettings()
    log_settings.enable_trace = args.debug
    log_settings.log_output = log_output_settings

    settings = lg.TestSettings()
    settings.FromConfig(mlperf_conf, "resnet50", args.scenario)
    settings.FromConfig(user_conf, "resnet50", args.scenario)
    settings.scenario = scenario
    settings.mode = lg.TestMode.PerformanceOnly
    if args.accuracy:
        settings.mode = lg.TestMode.AccuracyOnly
    if args.find_peak_performance:
        settings.mode = lg.TestMode.FindPeakPerformance

    if args.time:
        # override the time we want to run
        settings.min_duration_ms = args.time * MILLI_SEC
        settings.max_duration_ms = args.time * MILLI_SEC

    if args.qps:
        qps = float(args.qps)
        settings.server_target_qps = qps
        settings.offline_expected_qps = qps

    if count_override:
        settings.min_query_count = count
        settings.max_query_count = count

    if args.samples_per_query:
        settings.multi_stream_samples_per_query = args.samples_per_query
    if args.max_latency:
        settings.server_target_latency_ns = int(args.max_latency * NANO_SEC)
        settings.multi_stream_expected_latency_ns = int(args.max_latency * NANO_SEC)

    performance_sample_count = args.performance_sample_count if args.performance_sample_count else min(count, 500)
    sut = lg.ConstructSUT(issue_queries, flush_queries)
    qsl = lg.ConstructQSL(count, performance_sample_count, ds.load_query_samples, ds.unload_query_samples)

    result_dict = {"good": 0, "total": 0, "scenario": str(scenario)}
    runner.start_run(result_dict, args.accuracy)

    lg.StartTestWithLogSettings(sut, qsl, settings, log_settings, audit_config)

    if not last_timeing:
        last_timeing = runner.result_timing
    if args.accuracy:
        post_proc.finalize(result_dict, ds, output_dir=args.output)

    msg = add_results(final_results, "{}".format(scenario),
                result_dict, last_timeing, time.time() - ds.last_loaded, args.accuracy)

    runner.finish()
    lg.DestroyQSL(qsl)
    lg.DestroySUT(sut)

    # write final results
    if args.output:
        with open("results.json", "w") as f:
            json.dump(final_results, f, sort_keys=True, indent=4)

    logging.info(str(final_results))
    return msg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve()