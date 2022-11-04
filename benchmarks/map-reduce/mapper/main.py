# MIT License
#
# Copyright (c) 2021 Michal Baczun and EASE lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import print_function

import pickle
import sys
import grpc
import argparse
import logging as log
import socket
import boto3
import json
import resource
from io import StringIO ## for Python 3
import os
import time
from joblib import Parallel, delayed

# adding python tracing sources to the system path
sys.path.insert(0, os.getcwd() + '/../proto/')
sys.path.insert(0, os.getcwd() + '/../../../utils/tracing/python')
import tracing
import storage
import mapreduce_pb2_grpc
import mapreduce_pb2
import destination as XDTdst
import source as XDTsrc
import utils as XDTutil

from concurrent import futures

parser = argparse.ArgumentParser()
parser.add_argument("-dockerCompose", "--dockerCompose", dest="dockerCompose", default=False, help="Env docker compose")
parser.add_argument("-sp", "--sp", dest="sp", default="80", help="serve port")
parser.add_argument("-zipkin", "--zipkin", dest="zipkinURL",
                    default="http://zipkin.istio-system.svc.cluster.local:9411/api/v2/spans",
                    help="Zipkin endpoint url")

args = parser.parse_args()

if tracing.IsTracingEnabled():
    tracing.initTracer("mapper", url=args.zipkinURL)
    tracing.grpcInstrumentClient()
    tracing.grpcInstrumentServer()


# constants
INPUT_MAPPER_PREFIX = "artemiy/"
OUTPUT_MAPPER_PREFIX = "artemiy/task/mapper/"
INPUT_REDUCER_PREFIX = OUTPUT_MAPPER_PREFIX
OUTPUT_REDUCER_PREFIX = "artemiy/task/reducer/"
S3 = "S3"
XDT = "XDT"
ELASTICACHE = "ELASTICACHE"

# set aws credentials:
AWS_ID = os.getenv('AWS_ACCESS_KEY', "")
AWS_SECRET = os.getenv('AWS_SECRET_KEY', "")
AWS_ELASTICACHE_URL = os.getenv("AWS_ELASTICACHE_URL", "undefined.url")


class MapperServicer(mapreduce_pb2_grpc.MapperServicer):
    def __init__(self, transferType, XDTconfig=None):
        self.transferType = transferType
        self.mapperId = ""
        self.s3_client = boto3.resource(
            service_name='s3',
            region_name=os.getenv("AWS_REGION", 'us-west-1'),
            aws_access_key_id=AWS_ID,
            aws_secret_access_key=AWS_SECRET
        )

        if transferType == XDT:
            if XDTconfig is None:
                log.fatal("Empty XDT config")
            self.XDTclient = XDTsrc.XDTclient(XDTconfig)
            self.XDTconfig = XDTconfig

    def put(self, bucket, key, obj):
        msg = "Mapper uploading object with key '" + key + "' to " + self.transferType
        log.info(msg)
        log.info("object is of type %s", type(obj))

        with tracing.Span(msg):
            if self.transferType == S3 or self.transferType == ELASTICACHE:
                storage.put(key, obj)
            elif self.transferType == XDT:
                key = self.XDTclient.Put(payload=obj)

        return key

    def get(self, key):
        msg = "Mapper gets key '" + key + "' from " + self.transferType
        log.info(msg)
        with tracing.Span(msg):
            response = None
            if self.transferType == S3 or self.transferType == ELASTICACHE:
                storage.get(key)
            elif self.transferType == XDT:
                return XDTdst.Get(key, self.XDTconfig)

        # return pickle.loads(response['Body'].read())
        return response['Body'].read()

    def Map(self, request, context):
        mapper_id = request.mapperId
        log.info(f"Mapper {mapper_id} is invoked")

        dest_bucket = request.destBucket  # s3 bucket where the mapper will write the result
        src_bucket  = request.srcBucket   # s3 bucket where the mapper will search for input files
        src_keys    = request.keys        # src_keys is a list of input file names for this mapper
        job_id      = request.jobId
        n_reducers  = request.nReducers

        # make keys array from request
        src_keys = []
        for i, key in enumerate(request.keys):
            src_keys.append(key)

        print(src_keys, mapper_id)

        # aggr 
        output = {}
        line_count = 0
        err = ''

        # INPUT CSV => OUTPUT JSON

        start_time = time.time()
        log.info(f"Mapper {mapper_id}: fetch keys")
        with tracing.Span("Fetch keys"):
            start_time = 0
            content_list = []
            for grpc_key in src_keys:
                key = grpc_key.key
                key = INPUT_MAPPER_PREFIX + key
                obj = self.s3_client.Object(bucket_name=src_bucket, key=key)
                response = obj.get()
                contents = response['Body'].read().decode("utf-8")
                content_list.append(contents)
                # TODO self.get??

        with tracing.Span("process keys and shuffle"):
            log.info(f"Mapper {mapper_id}: process inputs")
            for contents in content_list:
                for line in contents.split('\n')[:-1]:
                    line_count +=1
                    try:
                        data = line.split(',')
                        srcIp = data[0][:8]
                        if srcIp not in output:
                            output[srcIp] = 0
                        output[srcIp] += float(data[3])
                    except getopt.GetoptError as e:
                        # print (e)
                        err += '%s' % e

            log.info(f"Mapper {mapper_id}: shuffle outputs")
            shuffle_output = []
            for i in range(n_reducers):
                reducer_output = {}
                shuffle_output.append(reducer_output)
            for srcIp in output.keys():
                reducer_num = hash(srcIp) & (n_reducers - 1)
                shuffle_output[reducer_num][srcIp] = output[srcIp]

        time_in_secs = (time.time() - start_time)

        response = mapreduce_pb2.MapReply()

        with tracing.Span("Save result"):
            write_tasks = []
            for to_reducer_id in range(n_reducers):
                mapper_fname = "%sjob_%s/shuffle_%s/map_%s" % (OUTPUT_MAPPER_PREFIX, job_id, to_reducer_id, mapper_id) 
        #        print(mapper_fname)
                write_tasks.append((dest_bucket, mapper_fname, pickle.dumps(shuffle_output[to_reducer_id])))

            keys = Parallel(backend="threading", n_jobs=n_reducers)(delayed(self.put)(*i) for i in write_tasks)
            for key in keys:
                grpc_keys = mapreduce_pb2.Keys()
                grpc_keys.key = key
                response.keys.append(grpc_keys)

            pret = [len(src_keys), line_count, time_in_secs, err]
        print("mapper" + str(mapper_id), pret)

        # return pret
        response.reply = "success"
        return response


def serve():
    transferType = os.getenv('TRANSFER_TYPE', S3)

    if transferType == S3 or transferType == ELASTICACHE:
        if transferType == S3:
            storage.init(S3, 'storage-module-test')
        elif transferType == ELASTICACHE:
            storage.init(ELASTICACHE, AWS_ELASTICACHE_URL)
        log.info("Using inline or s3 or elasticache transfers")

    XDTconfig = dict()
    if transferType == XDT:
        XDTconfig = XDTutil.loadConfig()
        log.info("XDT config:")
        log.info(XDTconfig)

    log.info("Using inline or s3 transfers")
    max_workers = int(os.getenv("MAX_SERVER_THREADS", 16))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    mapreduce_pb2_grpc.add_MapperServicer_to_server(
        MapperServicer(transferType=transferType, XDTconfig=XDTconfig), server)
    server.add_insecure_port('[::]:' + args.sp)
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    log.basicConfig(level=log.INFO)
    serve()
