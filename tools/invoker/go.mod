module github.com/vhive-serverless/vSwarm/tools/invoker

go 1.21.4

replace (
	github.com/vhive-serverless/vSwarm/tools/benchmarking_eventing => ../benchmarking_eventing
	github.com/vhive-serverless/vSwarm/tools/endpoint => ../endpoint
	github.com/vhive-serverless/vSwarm/utils/protobuf/helloworld => ../../utils/protobuf/helloworld
	github.com/vhive-serverless/vSwarm/utils/tracing/go => ../../utils/tracing/go
)

require (
	github.com/golang/protobuf v1.5.4
	github.com/google/uuid v1.6.0
	github.com/sirupsen/logrus v1.9.3
	github.com/vhive-serverless/vSwarm/tools/benchmarking_eventing v0.0.0-00010101000000-000000000000
	github.com/vhive-serverless/vSwarm/tools/endpoint v0.0.0-00010101000000-000000000000
	github.com/vhive-serverless/vSwarm/utils/protobuf/helloworld v0.0.0-00010101000000-000000000000
	github.com/vhive-serverless/vSwarm/utils/tracing/go v0.0.0-00010101000000-000000000000
	go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.53.0
	google.golang.org/grpc v1.65.0
)

require (
	github.com/containerd/log v0.1.0 // indirect
	github.com/go-logr/logr v1.4.2 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/openzipkin/zipkin-go v0.4.3 // indirect
	go.opentelemetry.io/otel v1.28.0 // indirect
	go.opentelemetry.io/otel/exporters/zipkin v1.28.0 // indirect
	go.opentelemetry.io/otel/metric v1.28.0 // indirect
	go.opentelemetry.io/otel/sdk v1.28.0 // indirect
	go.opentelemetry.io/otel/trace v1.28.0 // indirect
	golang.org/x/net v0.27.0 // indirect
	golang.org/x/sys v0.22.0 // indirect
	golang.org/x/text v0.16.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20240725223205-93522f1f2a9f // indirect
	google.golang.org/protobuf v1.34.2 // indirect
)
