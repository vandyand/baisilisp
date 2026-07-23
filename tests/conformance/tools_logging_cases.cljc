;; Portable clojure.tools.logging/basilisp.tools.logging public surface.
;;
;; Actual emitted log records are host-specific; local Basilisp tests verify the
;; Python logging bridge. This fixture locks public names and portable factory
;; behavior.

(require '[clojure.tools.logging :as log]
         '[clojure.tools.logging.impl :as impl])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :logging-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.logging
                                              :lpy 'basilisp.tools.logging))
                               %)
                   '[*force*
                     *logger-factory*
                     *logging-agent*
                     *tx-agent-levels*
                     debug
                     debugf
                     enabled?
                     error
                     errorf
                     fatal
                     fatalf
                     info
                     infof
                     log
                     log*
                     log-capture!
                     log-stream
                     log-uncapture!
                     logf
                     logp
                     spy
                     spyf
                     trace
                     tracef
                     warn
                     warnf
                     with-logs]))

(emit-case :impl-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.logging.impl
                                              :lpy 'basilisp.tools.logging.impl))
                               %)
                   '[Logger
                     LoggerFactory
                     cl-factory
                     class-found?
                     disabled-logger
                     disabled-logger-factory
                     enabled?
                     find-factory
                     get-logger
                     jul-factory
                     log4j-factory
                     log4j2-factory
                     name
                     slf4j-factory
                     write!]))

(emit-case :disabled-factory
           {:name (impl/name impl/disabled-logger-factory)
            :enabled? (impl/enabled? (impl/get-logger impl/disabled-logger-factory
                                                      "demo")
                                     :info)})
