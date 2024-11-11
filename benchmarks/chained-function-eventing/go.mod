module chained_function_eventing

go 1.21
toolchain go1.22.9

replace github.com/vhive-serverless/vSwarm/tools/benchmarking_eventing => ../../tools/benchmarking_eventing

require (
	github.com/cloudevents/sdk-go/v2 v2.15.2
	github.com/kelseyhightower/envconfig v1.4.0
	github.com/vhive-serverless/vSwarm/tools/benchmarking_eventing v0.0.0-20240422181019-5b1711d87c5d
	google.golang.org/grpc v1.68.0
	google.golang.org/protobuf v1.34.2
)

require (
	github.com/containerd/log v0.1.0 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/json-iterator/go v1.1.12 // indirect
	github.com/modern-go/concurrent v0.0.0-20180306012644-bacd9c7ef1dd // indirect
	github.com/modern-go/reflect2 v1.0.2 // indirect
	github.com/sirupsen/logrus v1.9.3 // indirect
	go.uber.org/multierr v1.11.0 // indirect
	go.uber.org/zap v1.27.0 // indirect
	golang.org/x/net v0.29.0 // indirect
	golang.org/x/sys v0.25.0 // indirect
	golang.org/x/text v0.18.0 // indirect
	golang.org/x/time v0.0.0-20220210224613-90d013bbcef8 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20240903143218-8af14fe29dc1 // indirect
)
