;; Execute the pinned upstream source and check its exported public spec.
#?(:lpy (load-file "tests/acceptance/upstream/cognitect-anomalies/adapters/clojure/spec/alpha.lpy"))

(load-file "tests/acceptance/upstream/cognitect-anomalies/upstream/src/cognitect/anomalies.cljc")

(println
 (pr-str
  #?(:clj (let [valid? (requiring-resolve 'clojure.spec.alpha/valid?)]
            {:valid (valid? :cognitect.anomalies/anomaly
                            {:cognitect.anomalies/category :cognitect.anomalies/not-found
                             :cognitect.anomalies/message "missing"})
             :missing-category (valid? :cognitect.anomalies/anomaly
                                       {:cognitect.anomalies/message "missing"})
             :invalid-category (valid? :cognitect.anomalies/anomaly
                                       {:cognitect.anomalies/category :example/unknown})})
     :lpy (let [valid? basilisp.spec.alpha/valid?]
            {:valid (valid? :cognitect.anomalies/anomaly
                            {:cognitect.anomalies/category :cognitect.anomalies/not-found
                             :cognitect.anomalies/message "missing"})
             :missing-category (valid? :cognitect.anomalies/anomaly
                                       {:cognitect.anomalies/message "missing"})
             :invalid-category (valid? :cognitect.anomalies/anomaly
                                       {:cognitect.anomalies/category :example/unknown})}))))
