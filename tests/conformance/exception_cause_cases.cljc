(ns conformance.exception-cause-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [cause (ex-info "inner cause" {:layer :inner})
      outer (ex-info "outer wrapper" {:layer :outer} cause)
      mapped (Throwable->map outer)]
  (emit-case :explicit-ex-info-cause
             {:message       (ex-message outer)
              :data          (ex-data outer)
              :cause-message (ex-message (ex-cause outer))
              :cause-data    (ex-data (ex-cause outer))
              :same-cause?   (identical? cause (ex-cause outer))
              :mapped-cause  (:cause mapped)
              :mapped-data   (:data mapped)
              :via-messages  (mapv :message (:via mapped))
              :via-data      (mapv :data (:via mapped))}))

(let [caught (try
               (try
                 (throw (ex-info "inner thrown" {:layer :inner}))
                 (catch #?(:clj Throwable :lpy python/Exception) cause
                   (throw (ex-info "outer thrown"
                                   {:layer :outer
                                    :clojure.error/phase :execution}
                                   cause))))
               (catch #?(:clj Throwable :lpy python/Exception) e
                 e))
      mapped (Throwable->map caught)
      first-via (first (:via mapped))]
  (emit-case :throwable-map-structured-shape
             {:message          (ex-message caught)
              :data             (ex-data caught)
              :phase            (:phase mapped)
              :mapped-cause     (:cause mapped)
              :mapped-data      (:data mapped)
              :via-count        (count (:via mapped))
              :via-messages     (mapv :message (:via mapped))
              :via-data         (mapv :data (:via mapped))
              :via-at?          (mapv #(contains? % :at) (:via mapped))
              :first-at-vector? (vector? (:at first-via))
              :first-at-count   (count (:at first-via))
              :trace-vector?    (vector? (:trace mapped))
              :trace-non-empty? (pos? (count (:trace mapped)))
              :trace-entry-size (count (first (:trace mapped)))}))
