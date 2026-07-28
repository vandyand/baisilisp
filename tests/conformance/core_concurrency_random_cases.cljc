;; Portable clojure.core concurrency, agent, and random-helper residual
;; semantics. Nondeterministic values are normalized into stable shape/range
;; predicates before comparison.

#?(:clj (import '[java.util.concurrent Executors TimeUnit])
   :lpy (import [basilisp.lang.futures :as futures]
                time))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn make-executor [prefix workers]
  #?(:clj (Executors/newFixedThreadPool workers)
     :lpy (futures/ThreadPoolExecutor ** :max-workers workers
                                      :thread-name-prefix prefix)))

(defn shutdown-executor [executor]
  #?(:clj (do
            (.shutdown executor)
            (.awaitTermination executor 5 TimeUnit/SECONDS))
     :lpy (do
            (.shutdown executor)
            true)))

(defn throwable-message [e]
  #?(:clj (.getMessage e)
     :lpy (first (.-args e))))

(defn sleep-ms [ms]
  #?(:clj (Thread/sleep ms)
     :lpy (time/sleep (/ ms 1000.0))))

(defn wait-until [pred]
  (loop [remaining 100]
    (cond
      (pred) true
      (zero? remaining) false
      :else (do
              (sleep-ms 10)
              (recur (dec remaining))))))

(emit-case :parallel-helper-contracts
           {:pmap [(vec (pmap inc []))
                   (vec (pmap inc (range 8)))
                   (vec (pmap + (range 5) (range 10 15)))
                   (vec (take 6 (pmap #(* % %) (range 20))))]
            :pcalls [(vec (pcalls))
                     (vec (pcalls #(+ 1 2)
                                  #(* 3 4)
                                  #(apply str [:a :b])))]
            :pvalues [(vec (pvalues))
                      (vec (pvalues (+ 1 2)
                                    (* 3 4)
                                    (apply str [:a :b])))]})

(emit-case :parallel-seeded-stress
           (let [inputs (range -20 21)]
             {:single (vec (pmap #(+ (* % %) %) inputs))
              :multi (vec (pmap (fn [a b c]
                                   (+ (* a b) c))
                                 inputs
                                 (reverse inputs)
                                 (repeat 3)))
              :pcalls (let [fs (mapv (fn [n]
                                       (fn [] [n (* n n)]))
                                     (range 12))]
                        (vec (apply pcalls fs)))}))

(emit-case :random-helper-contracts
           (let [rand-values (repeatedly 40 rand)
                 scaled-values (repeatedly 40 #(rand 7.5))
                 ints (repeatedly 80 #(rand-int 9))
                 choices [:a :b :c :d]
                 nths (repeatedly 40 #(rand-nth choices))
                 uuid-values (cons (random-uuid) (repeatedly 19 random-uuid))
                 shuffled (repeatedly 20 #(shuffle choices))]
             {:rand [(every? double? rand-values)
                     (every? #(< -0.000000001 % 1.000000001) rand-values)
                     (every? double? scaled-values)
                     (every? #(< -0.000000001 % 7.500000001) scaled-values)]
              :rand-int [(every? integer? ints)
                         (every? #(<= 0 % 8) ints)
                         (= #{0} (set (repeatedly 20 #(rand-int 1))))]
              :rand-nth [(every? (set choices) nths)
                         (contains? (set choices) (rand-nth '(:a :b :c :d)))]
              :random-sample [(vec (random-sample 0.0 (range 8)))
                              (vec (random-sample 1.0 (range 8)))
                              (into [] (random-sample 0.0) (range 8))
                              (into [] (random-sample 1.0) (range 8))]
              :random-uuid [(every? uuid? uuid-values)
                            (every? #(= 4 #?(:clj (.version %)
                                             :lpy (.-version %)))
                                    uuid-values)
                            (= 20 (count (set uuid-values)))]
              :shuffle [(every? #(= (count choices) (count %)) shuffled)
                        (every? #(= (set choices) (set %)) shuffled)]}))

(emit-case :agent-send-restart-and-error-contracts
           (let [a (agent 0)
                 b (agent 10)
                 via-executor (make-executor "fixture-via" 1)]
             (try
               (send-off a + 2)
               (send-via via-executor b + 5)
               (clojure.core/await a b)
               (let [failed (agent 1)]
                 (send failed (fn [_]
                                (throw (#?(:clj RuntimeException.
                                           :lpy python/RuntimeError)
                                        "restartable"))))
                 (wait-until #(some? (agent-error failed)))
                 (rejected? #(clojure.core/await failed))
                 (let [failed-before [(true? (some? (agent-error failed)))
                                      @failed]
                       restarted (restart-agent failed 7)
                       _sent (send failed + 3)
                       _awaited (clojure.core/await failed)]
                   {:send-off @a
                    :send-via @b
                    :failed-before failed-before
                    :restart [restarted
                              @failed
                              (nil? (agent-error failed))]}))
               (finally
                 (shutdown-executor via-executor)))))

(emit-case :agent-error-mode-and-handler-contracts
           (let [seen (promise)
                 a (agent 0)]
             (set-error-mode! a :continue)
             (set-error-handler! a (fn [ag err]
                                     (deliver seen [(identical? ag a)
                                                    (throwable-message err)])))
             (send a (fn [_]
                       (throw (#?(:clj RuntimeException.
                                  :lpy python/RuntimeError)
                               "handled"))))
             (send a + 4)
             (clojure.core/await a)
             {:mode (error-mode a)
              :handler? (true? (some? (error-handler a)))
              :seen (deref seen 1000 :timeout)
              :state @a
              :error-cleared? (nil? (agent-error a))}))

(shutdown-agents)

(emit-case :agent-global-executor-contracts
           (let [send-executor (make-executor "fixture-send" 1)
                 send-off-executor (make-executor "fixture-send-off" 1)
                 a (agent 0)
                 b (agent 100)]
             (try
               (set-agent-send-executor! send-executor)
               (set-agent-send-off-executor! send-off-executor)
               (send a + 11)
               (send-off b + 13)
               (clojure.core/await a b)
               {:send @a
                :send-off @b}
               (finally
                 (shutdown-executor send-executor)
                 (shutdown-executor send-off-executor)))))

(shutdown-agents)
