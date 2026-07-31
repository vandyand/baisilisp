(ns acceptance.core-async.workflow
  (:require [clojure.core.async :as async]))

(defn drain
  "Synchronously drain channel values until close."
  [channel]
  (loop [acc   []
         value (async/<!! channel)]
    (if (some? value)
      (recur (conj acc value) (async/<!! channel))
      acc)))

(defn drain-go
  "Return a go result channel containing all channel values until close."
  [channel]
  (async/go-loop [acc   []
                  value (async/<! channel)]
    (if (some? value)
      (recur (conj acc value) (async/<! channel))
      acc)))

(defn go-transform-summary
  "Run a portable go-loop transform over a finite source channel."
  []
  (async/<!!
   (async/go
     (let [input  (async/to-chan! (range 8))
           output (async/chan 4)
           done   (async/go-loop [value (async/<! input)]
                    (if (some? value)
                      (do
                        (async/>! output [value (inc value)])
                        (recur (async/<! input)))
                      (do
                        (async/close! output)
                        :complete)))]
       [[:values (async/<! (drain-go output))]
        [:done   (async/<! done)]]))))

(defn selection-summary
  "Exercise alt!, timeout, priority, put clauses, and nested parking choices."
  []
  (let [priority-first  (async/chan 1)
        priority-second (async/chan 1)
        nested-first    (async/chan 1)
        nested-second   (async/chan 1)
        target          (async/chan 1)]
    (async/>!! priority-first :first)
    (async/>!! priority-second :second)
    (async/>!! nested-first :first)
    (async/>!! nested-second :second)
    [[:priority
     (async/<!! (async/go
                  (async/alt! priority-second ([value port]
                                               [value (identical? port priority-second)])
                              priority-first :first-branch
                              :priority true)))]
     [:nested
     (async/<!! (async/go
                  (async/alt! nested-first ([first-value first-port]
                                           (async/alt! nested-second ([second-value second-port]
                                                                     [first-value
                                                                      (identical? first-port nested-first)
                                                                      second-value
                                                                      (identical? second-port nested-second)])))
                              :priority true)))]
     [:put
     (let [result (async/<!! (async/go
                               (async/alt! [[target :written]]
                                           ([accepted? port]
                                            [accepted? (identical? port target)]))))]
       [result (async/<!! target)])]
     [:timeout
     (async/<!! (async/go
                  (let [timer (async/timeout 1)]
                    (async/alt! timer ([value port]
                                       [(nil? value) (identical? port timer)])))))]
     ]))

(defn pipeline-summary
  "Exercise ordered transducer pipelines and close propagation."
  []
  (async/<!!
   (async/go
     (let [source      (async/to-chan! [1 2 3 4])
           destination (async/chan 4)]
       (async/pipeline 2 destination (map inc) source)
       (async/<! (drain-go destination))))))

(defn collection-summary
  "Exercise collection/channel combinators in ordinary application shape."
  []
  (async/<!!
   (async/go
     (let [merged     (async/merge [(async/to-chan! [3 1])
                                    (async/to-chan! [2 4])]
                                   4)
           [even odd] (async/split even? (async/to-chan! (range 6)) 3 3)
           mapped     (async/mapcat< (fn [value] [value (* value value)])
                                     (async/to-chan! [1 2 3])
                                     6)
           stream-values [:basilisp.core.async/none
                          :alpha
                          :alpha
                          :beta
                          4
                          4
                          :gamma]
           pairwise      (async/map vector
                                    [(async/to-chan! (range 4))
                                     (async/to-chan! (range 10 14))]
                                    4)
           partitioned   (async/partition 3
                                           (async/to-chan! stream-values)
                                           4)
           by-key        (async/partition-by #(if (keyword? %)
                                                %
                                                (mod % 3))
                                             (async/to-chan! stream-values)
                                             4)
           deduped       (async/unique (async/to-chan! stream-values) 4)]
       [[:merge     (vec (sort (async/<! (drain-go merged))))]
        [:split     [(async/<! (drain-go even)) (async/<! (drain-go odd))]]
        [:into      (async/<! (async/into [] (async/to-chan! [1 2 3])))]
        [:reduce    (async/<! (async/reduce + 0 (async/to-chan! [1 2 3 4])))]
        [:transduce (async/<! (async/transduce (map inc)
                                               +
                                               0
                                               (async/to-chan! [1 2 3])))]
        [:transform (async/<! (drain-go mapped))]
        [:stream    [[:map          (async/<! (drain-go pairwise))]
                     [:partition    (async/<! (drain-go partitioned))]
                     [:partition-by (async/<! (drain-go by-key))]
                     [:unique       (async/<! (drain-go deduped))]]]]))))

(defn routing-summary
  "Exercise finite mult and pub routing with deterministic data."
  []
  (async/<!!
   (async/go
     (let [source     (async/chan 2)
           m          (async/mult source)
           left       (async/chan 2)
           right      (async/chan 2)
           pub-source (async/chan 4)
           p          (async/pub pub-source :topic)
           alpha      (async/chan 2)
           beta       (async/chan 2)]
       (async/tap m left)
       (async/tap m right)
       (async/>! source :one)
       (let [first-pair [(async/<! left) (async/<! right)]]
         (async/untap m right)
         (async/>! source :two)
         (let [left-only [(async/<! left) (async/poll! right)]]
           (async/sub p :a alpha)
           (async/sub p :b beta)
           (async/>! pub-source {:topic :a :value [:a 1]})
           (async/>! pub-source {:topic :b :value [:b 2]})
           (async/>! pub-source {:topic :c :value [:c 3]})
           (let [published [(async/<! alpha) (async/<! beta)]]
             (async/unsub p :b beta)
             (async/>! pub-source {:topic :b :value [:b 4]})
             (let [unsubbed (async/poll! beta)]
               (async/close! source)
               (async/close! pub-source)
               [[:mult [first-pair left-only]]
                [:pub  [(mapv :value published) unsubbed]]]))))))))

(defn stress-summary
  "Run a deterministic go-parking stress probe over independent channels."
  []
  (let [inputs  (doall (map (fn [idx]
                              (let [channel (async/chan 1)]
                                (async/>!! channel idx)
                                channel))
                            (range 32)))
        results (doall (map (fn [channel]
                            (async/go
                                (let [value (async/<! channel)]
                                  [value (inc value)])))
                            inputs))]
    (vec (map async/<!! results))))
