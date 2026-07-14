# cognitect-labs/anomalies acceptance snapshot

- Upstream: https://github.com/cognitect-labs/anomalies
- Pinned revision: `6e69216658c8097d2f34dd773634f1750cc751f9`
- Upstream license: Apache License 2.0
- Source scope: `upstream/src/cognitect/anomalies.cljc`

The upstream project contains no test source. The acceptance entrypoint loads
the pinned source and verifies its public `::anomaly` spec contract in both
runtimes. Its sole Basilisp adapter is the standard namespace substitution
`clojure.spec.alpha -> basilisp.spec.alpha`; upstream source is unchanged.
