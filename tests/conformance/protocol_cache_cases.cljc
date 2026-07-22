(ns conformance.protocol-cache-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defprotocol CacheParity
  (cache-parity [this]))

(defrecord CacheParityValue []
  CacheParity
  (cache-parity [_] :direct))

(let [value (->CacheParityValue)
      interface #?(:clj (:on-interface CacheParity)
                   :lpy (:interface CacheParity))
      cached (-cache-protocol-fn cache-parity value interface (fn [_] :cached-direct))]
  (emit-case :protocol-cache-reset
             {:before       (cache-parity value)
              :reset-result (-reset-methods CacheParity)
              :after        (cache-parity value)
              :cached       (cached value)}))
