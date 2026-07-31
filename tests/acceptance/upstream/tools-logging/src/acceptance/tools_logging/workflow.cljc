(ns acceptance.tools-logging.workflow
  (:require [clojure.string :as str]
            [clojure.tools.logging :as log]
            [clojure.tools.logging.impl :as impl]
            [clojure.tools.logging.readable :as readable]))

(def levels [:trace :debug :info :warn :error :fatal])

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn public-names [ns-sym]
  (sort
   (remove #(str/starts-with? % "clojure.tools.logging.proxy$")
           (map name (keys (ns-publics ns-sym))))))

(defn public-summary []
  {:logging (public-names 'clojure.tools.logging)
   :impl (public-names 'clojure.tools.logging.impl)
   :readable (public-names 'clojure.tools.logging.readable)})

(defn capture-factory [enabled-levels]
  (let [records (atom [])
        logger (reify impl/Logger
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

(defn portable-records [records]
  (mapv (fn [{:keys [level throwable? message]}]
          {:level level
           :throwable? throwable?
           :message message})
        records))

(defn portable-record-shapes [records]
  (mapv (fn [{:keys [level throwable? message]}]
          {:level level
           :throwable? throwable?
           :message-empty? (empty? message)})
        records))

(defn factory-summary []
  {:disabled {:name (impl/name impl/disabled-logger-factory)
              :enabled? (impl/enabled?
                         (impl/get-logger impl/disabled-logger-factory "demo")
                         :info)
              :direct-disabled? (not (impl/enabled? impl/disabled-logger :info))
              :write-result (impl/write! impl/disabled-logger :info nil "ignored")}
   :boundaries {:class-present #?(:clj (impl/class-found? "java.lang.String")
                                  :lpy (impl/class-found? "logging.Logger"))
                :class-missing (impl/class-found?
                                "definitely.missing.logging.Backend")
                :slf4j-missing? (nil? (impl/slf4j-factory))
                :cl-missing? (nil? (impl/cl-factory))
                :log4j2-missing? (nil? (impl/log4j2-factory))
                :log4j-missing? (nil? (impl/log4j-factory))
                :jul-boundary? #?(:clj (some? (impl/jul-factory))
                                  :lpy (nil? (impl/jul-factory)))
                :find-factory? (some? (impl/find-factory))}})

(defn macro-gating-summary []
  (let [{:keys [factory records]} (capture-factory
                                   #{:debug :info :warn :error :fatal})
        expensive (atom [])
        thrown #?(:clj (Exception. "fixture")
                  :lpy (python/Exception "fixture"))
        enabled (binding [log/*logger-factory* factory]
                  {:debug (log/enabled? :debug)
                   :trace (log/enabled? :trace)})
        spy-value (binding [log/*logger-factory* factory]
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
        spyf-value (binding [log/*logger-factory* factory]
                     (log/spyf :debug "spyf=%s" (inc 4)))
        logger (impl/get-logger factory 'fixture.direct)]
    (log/log* logger :info nil "star")
    {:expensive @expensive
     :enabled enabled
     :spy-value spy-value
     :spyf-value spyf-value
     :records (portable-records @records)}))

(defn stream-capture-summary []
  (let [{:keys [factory records]} (capture-factory #{:trace :error})
        dynamic-boundaries {:force (some? log/*force*)
                            :logging-agent-boundary #?(:clj
                                                       (some? log/*logging-agent*)
                                                       :lpy
                                                       (nil? log/*logging-agent*))
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
     :records (portable-records @records)}))

(defn readable-summary []
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

(defn arity-summary []
  (let [{:keys [factory records]} (capture-factory #{:fatal :info})]
    (binding [log/*logger-factory* factory]
      (log/log :info "default")
      (log/log 'fixture.custom :fatal nil "custom")
      (log/log factory 'fixture.factory :debug nil "suppressed")
      (log/log factory 'fixture.factory :fatal nil "factory"))
    (portable-records @records)))

(defn boundary-summary []
  (let [{:keys [factory records]} (capture-factory #{:debug :info :warn :error})
        thrown #?(:clj (Exception. "fixture")
                  :lpy (python/Exception "fixture"))
        realized (atom [])]
    (binding [log/*logger-factory* factory]
      (log/warn thrown)
      (log/error thrown "with message")
      (readable/warn thrown)
      (readable/error thrown {:kind :readable})
      (log/trace (do (swap! realized conj :root-trace) thrown))
      (readable/trace (do (swap! realized conj :readable-trace) thrown))
      (log/debug (do (swap! realized conj :root-debug) thrown))
      (readable/info (do (swap! realized conj :readable-info) thrown)))
    {:throwable-arity-records (portable-record-shapes @records)
     :realized @realized
     :readable-strings (let [{:keys [factory records]} (capture-factory #{:info})
                             runtime-string (str "runtime")]
                         (binding [log/*logger-factory* factory]
                           (readable/info "literal" (sorted-map :a 1) "tail")
                           (readable/info runtime-string)
                           (readable/infof "fmt=%s/%s"
                                           "literal"
                                           (sorted-map :b 2)))
                         (mapv :message @records))}))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn generated-level-set [seed]
  (set (keep-indexed (fn [idx level]
                       (when (pos? (bit-and seed (bit-shift-left 1 idx)))
                         level))
                     levels)))

(defn generated-case [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        enabled-levels (generated-level-set s1)
        {:keys [factory records]} (capture-factory enabled-levels)
        realized (atom [])]
    (binding [log/*logger-factory* factory]
      (doseq [level levels]
        (log/logp level
                  (do (swap! realized conj [:logp level])
                      (str "message-" (name level))))
        (log/logf level "fmt-%s" (name level))))
    {:seed seed
     :enabled (vec (sort enabled-levels))
     :realized @realized
     :record-count (count @records)
     :records (portable-records @records)
     :expected-record-count (* 2 (count enabled-levels))
     :next-seed s2}))

(defn generated-summary []
  (loop [remaining 48
         seed 324508639
         result []]
    (if (zero? remaining)
      result
      (let [case (generated-case seed)]
        (recur (dec remaining)
               (:next-seed case)
               (conj result (dissoc case :next-seed)))))))
