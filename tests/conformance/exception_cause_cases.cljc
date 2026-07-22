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
