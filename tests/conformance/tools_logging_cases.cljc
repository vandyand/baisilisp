;; Portable clojure.tools.logging/basilisp.tools.logging public surface.
;;
;; Actual emitted log records are host-specific; local Basilisp tests verify the
;; Python logging bridge. This fixture locks public names and portable factory
;; behavior.

(require '[clojure.tools.logging :as log]
         '[clojure.tools.logging.impl :as impl]
         '[clojure.tools.logging.readable :as readable])

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

(emit-case :readable-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.logging.readable
                                              :lpy 'basilisp.tools.logging.readable))
                               %)
                   '[debug
                     debugf
                     error
                     errorf
                     fatal
                     fatalf
                     info
                     infof
                     logf
                     logp
                     spyf
                     trace
                     tracef
                     warn
                     warnf]))

(emit-case :disabled-factory
           {:name (impl/name impl/disabled-logger-factory)
            :enabled? (impl/enabled? (impl/get-logger impl/disabled-logger-factory
                                                      "demo")
                                     :info)
            :direct-disabled? (not (impl/enabled? impl/disabled-logger :info))
            :write-result (impl/write! impl/disabled-logger :info nil "ignored")})

(emit-case :impl-factory-boundaries
           {:class-present #?(:clj (impl/class-found? "java.lang.String")
                              :lpy (impl/class-found? "logging.Logger"))
            :class-missing (impl/class-found? "definitely.missing.logging.Backend")
            :slf4j-missing? (nil? (impl/slf4j-factory))
            :cl-missing? (nil? (impl/cl-factory))
            :log4j2-missing? (nil? (impl/log4j2-factory))
            :log4j-missing? (nil? (impl/log4j-factory))
            :jul-boundary? #?(:clj (some? (impl/jul-factory))
                              :lpy (nil? (impl/jul-factory)))
            :find-factory? (some? (impl/find-factory))})

(defn capture-factory
  [enabled-levels]
  (let [records (atom [])
        logger  (reify impl/Logger
                  (enabled? [_ level]
                    (contains? enabled-levels level))
                  (write! [_ level throwable message]
                    (swap! records conj
                           {:level level
                            :throwable? (boolean throwable)
                            :message (str message)})
                    nil))
        factory (reify impl/LoggerFactory
                  (name [_] "fixture-capture")
                  (get-logger [_ logger-ns]
                    logger))]
    {:factory factory
     :records records}))

(emit-case :logging-macro-gating-and-formatting
           (let [{:keys [factory records]} (capture-factory #{:debug :info :warn :error :fatal})
                 expensive                (atom [])
                 thrown                   #?(:clj (Exception. "fixture")
                                             :lpy (python/Exception "fixture"))
                 enabled                  (binding [log/*logger-factory* factory]
                                            {:debug (log/enabled? :debug)
                                             :trace (log/enabled? :trace)})
                 spy-value                (binding [log/*logger-factory* factory]
                                            (log/trace (swap! expensive conj :trace))
                                            (log/debug (swap! expensive conj :debug))
                                            (log/debugf "dbg-%s" "f")
                                            (log/info "plain" "message")
                                            (log/infof "info-%s" "f")
                                            (log/warn thrown "warned")
                                            (log/warnf "warn-%s" "f")
                                            (log/errorf "err-%s-%d" "x" 7)
                                            (log/fatal "fatal" "message")
                                            (log/fatalf "fatal-%s" "f")
                                            (log/logp :warn "lp" "more")
                                            (log/logf :info "lf-%s" "x")
                                            (log/spy :info (+ 1 2)))
                 spyf-value               (binding [log/*logger-factory* factory]
                                            (log/spyf :debug "spyf=%s" (inc 4)))
                 logger                   (impl/get-logger factory 'fixture.direct)]
             (log/log* logger :info nil "star")
             {:expensive @expensive
              :enabled enabled
              :spy-value spy-value
              :spyf-value spyf-value
              :records @records}))

(emit-case :logging-stream-capture-and-extra-levels
           (let [{:keys [factory records]} (capture-factory #{:trace :error})
                 dynamic-boundaries {:force (some? log/*force*)
                                     :logging-agent-boundary #?(:clj (some? log/*logging-agent*)
                                                                :lpy (nil? log/*logging-agent*))
                                     :tx-agent-levels (some? log/*tx-agent-levels*)}
                 stream? (some? (log/log-stream :info "fixture.stream"))
                 capture? (try
                            (log/log-capture! "fixture.stream")
                            (log/log-uncapture!)
                            true
                            (catch #?(:clj Throwable :lpy python/Exception) _
                              false))
                 with-logs-result (log/with-logs "fixture.stream"
                                    :with-logs-result)]
             (binding [log/*logger-factory* factory]
               (log/tracef "trace-%s" "f")
               (log/error "err" "message"))
             {:dynamic-boundaries dynamic-boundaries
              :stream? stream?
              :capture? capture?
              :with-logs-result with-logs-result
              :records @records}))

(emit-case :readable-direct-public-macro-smoke
           (let [{:keys [factory records]} (capture-factory #{})]
             (binding [log/*logger-factory* factory]
               (readable/trace "trace")
               (readable/tracef "tracef=%s" :v)
               (readable/debug "debug")
               (readable/debugf "debugf=%s" :v)
               (readable/info "info")
               (readable/infof "infof=%s" :v)
               (readable/warn "warn")
               (readable/warnf "warnf=%s" :v)
               (readable/error "error")
               (readable/errorf "errorf=%s" :v)
               (readable/fatal "fatal")
               (readable/fatalf "fatalf=%s" :v)
               (readable/logp :info "logp")
               (readable/logf :info "logf=%s" :v)
               {:spyf (readable/spyf :debug "spyf=%s" :result)
                :records @records})))

(emit-case :logging-explicit-log-arities
           (let [{:keys [factory records]} (capture-factory #{:fatal :info})]
             (binding [log/*logger-factory* factory]
               (log/log :info "default")
               (log/log 'fixture.custom :fatal nil "custom")
               (log/log factory 'fixture.factory :debug nil "suppressed")
               (log/log factory 'fixture.factory :fatal nil "factory"))
             @records))

(defn portable-records
  [records]
  (mapv (fn [{:keys [level throwable? message]}]
          {:level level
           :throwable? throwable?
           :message-empty? (empty? message)})
        records))

(emit-case :adversarial-throwable-arity-boundaries
           (let [{:keys [factory records]} (capture-factory #{:debug :info :warn :error})
                 thrown #?(:clj (Exception. "fixture")
                           :lpy (python/Exception "fixture"))
                 realized (atom [])]
             (binding [log/*logger-factory* factory]
               ;; A throwable with no message args is a normal message. Only
               ;; throwable + message uses the throwable slot.
               (log/warn thrown)
               (log/error thrown "with message")
               (readable/warn thrown)
               (readable/error thrown {:kind :readable})
               ;; Disabled optimized paths must remain lazy.
               (log/trace (do (swap! realized conj :root-trace) thrown))
               (readable/trace (do (swap! realized conj :readable-trace) thrown))
               ;; Enabled optimized paths realize once and still do not use the
               ;; throwable slot when there are no message args.
               (log/debug (do (swap! realized conj :root-debug) thrown))
               (readable/info (do (swap! realized conj :readable-info) thrown)))
             {:records (portable-records @records)
              :realized @realized}))

(emit-case :adversarial-readable-string-boundaries
           (let [{:keys [factory records]} (capture-factory #{:info})
                 runtime-string (str "runtime")]
             (binding [log/*logger-factory* factory]
               (readable/info "literal" (sorted-map :a 1) "tail")
               (readable/info runtime-string)
               (readable/infof "fmt=%s/%s" "literal" (sorted-map :b 2)))
             (mapv :message @records)))
