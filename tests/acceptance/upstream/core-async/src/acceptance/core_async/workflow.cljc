(ns acceptance.core-async.workflow
  (:require [clojure.core.async :as async]
            [clojure.core.async.impl.ioc-macros :as ioc]))

#?(:clj (import '[java.util.concurrent.atomic AtomicReferenceArray]))

(def supported-publics
  '#{buffer dropping-buffer sliding-buffer
     Mux Mult Pub Mix
     chan close! offer! poll! put! take!
     alts! timeout pipe pipeline
     promise-chan
     pipeline-async pipeline-blocking
     to-chan to-chan! to-chan!!
     onto-chan onto-chan! onto-chan!!
     merge split take
     into reduce transduce
     map partition partition-by unique
     unblocking-buffer?
     map< map> filter< filter>
     remove< remove> mapcat< mapcat>
     muxch*
     mult tap untap untap-all
     tap* untap* untap-all*
     pub sub unsub unsub-all
     sub* unsub* unsub-all*
     mix admix unmix unmix-all
     admix* unmix* unmix-all*
     toggle solo-mode
     toggle* solo-mode*
     <!! >!! alts!! alt!! do-alt
     fn-handler do-alts defblockingop
     go go-loop <! >! alt! ioc-alts!
     thread thread-call io-thread})

(defn public-surface-summary
  "Prove the maintained compatibility facade has neither missing nor accidental
  extra public names."
  []
  (let [publics (set (keys (ns-publics 'clojure.core.async)))]
    [[:exact? (= publics supported-publics)]
     [:missing (vec (sort (remove publics supported-publics)))]
     [:extra (vec (sort (remove supported-publics publics)))]]))

(defn ioc-boundary-summary
  "Classify direct ioc-alts! use as Basilisp's explicit unsupported IOC
  state-machine boundary while preserving the public name for source loading."
  []
  #?(:clj [[:public? true]
           [:boundary :unsupported-ioc-state-machine]
           [:required :compiler-generated-ioc]
           [:retains-inputs? true]]
     :lpy (try
            (async/ioc-alts! :state :block [:port])
            [[:public? true]
             [:boundary :not-rejected]
             [:required nil]
             [:retains-inputs? false]]
            (catch Exception e
              (let [data (ex-data e)]
                [[:public? (contains? (set (keys (ns-publics 'clojure.core.async)))
                                      'ioc-alts!)]
                 [:boundary (:basilisp.core.async/boundary data)]
                 [:required (:basilisp.core.async/required data)]
                 [:retains-inputs? (= [:state :block [:port] nil]
                                      [(:state data)
                                       (:cont-block data)
                                       (:ports data)
                                       (:opts data)])]])))))

(def ioc-publics
  '#{BINDINGS-IDX EXCEPTION-FRAMES FN-IDX STATE-IDX USER-START-IDX VALUE-IDX
     aget-object aset-all! aset-object async-custom-terminators put!
     return-chan run-state-machine run-state-machine-wrapped take!})

(defn ioc-state-array []
  #?(:clj (AtomicReferenceArray. 8)
     :lpy (object-array 8)))

(defn ioc-state-values [state]
  (vec (map #(ioc/aget-object state %) (range 8))))

(defn ioc-make-state [f]
  (doto (ioc-state-array)
    (ioc/aset-object ioc/FN-IDX f)
    (ioc/aset-object ioc/STATE-IDX 0)
    (ioc/aset-object ioc/VALUE-IDX :initial)
    (ioc/aset-object ioc/USER-START-IDX (async/chan 1))))

(defn ioc-helper-summary
  "Exercise the public runtime helpers targeted by generated IOC state
  machines without claiming compiler-produced IOC transformation."
  []
  (let [publics      (set (keys (ns-publics 'clojure.core.async.impl.ioc-macros)))
        array-state  (ioc-state-array)
        _            (ioc/aset-object array-state 7 :seven)
        _            (ioc/aset-all! array-state 0 :zero 2 :two 5 :five)
        calls        (atom [])
        run-state    (ioc-make-state
                      (fn [state]
                        (swap! calls conj [(ioc/aget-object state ioc/STATE-IDX)
                                           (ioc/aget-object state ioc/VALUE-IDX)])
                        (ioc/aset-all! state
                                       ioc/VALUE-IDX :next
                                       ioc/STATE-IDX 1)
                        :step-done))
        return-state (ioc-make-state (fn [_] :unused))
        out          (ioc/aget-object return-state ioc/USER-START-IDX)
        take-channel (async/chan 1)
        take-state   (ioc-make-state (fn [_] :unused))
        put-channel  (async/chan 1)
        put-state    (ioc-make-state (fn [_] :unused))]
    (async/>!! take-channel :ready)
    [[:surface {:exact? (= publics ioc-publics)
                :missing (vec (sort (remove publics ioc-publics)))
                :extra (vec (sort (remove ioc-publics publics)))}]
     [:constants [ioc/FN-IDX
                  ioc/STATE-IDX
                  ioc/VALUE-IDX
                  ioc/BINDINGS-IDX
                  ioc/EXCEPTION-FRAMES
                  ioc/USER-START-IDX]]
     [:array [(ioc/aget-object array-state 5)
              (ioc-state-values array-state)]]
     [:run [(ioc/run-state-machine run-state)
            @calls
            (ioc/aget-object run-state ioc/VALUE-IDX)
            (ioc/aget-object run-state ioc/STATE-IDX)]]
     [:return [(identical? out (ioc/return-chan return-state :returned))
               (async/<!! out)
               (async/<!! out)]]
     [:ready {:take [(ioc/take! take-state 7 take-channel)
                     (ioc/aget-object take-state ioc/VALUE-IDX)
                     (ioc/aget-object take-state ioc/STATE-IDX)]
              :put [(ioc/put! put-state 9 put-channel :value)
                    (async/<!! put-channel)
                    (ioc/aget-object put-state ioc/VALUE-IDX)
                    (ioc/aget-object put-state ioc/STATE-IDX)]}]
     [:terminators ioc/async-custom-terminators]]))

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
  "Exercise finite mult, pub, and mix routing with deterministic data."
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
           beta       (async/chan 2)
           return-out (async/chan 4)
           return-mx  (async/mix return-out)
           return-in  (async/chan 4)
           mix-out    (async/chan 8)
           mx         (async/mix mix-out)
           x          (async/chan 8)
           y          (async/chan 8)]
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
               (let [return-contracts [(true? (async/admix return-mx return-in))
                                       (true? (async/toggle return-mx {return-in {:mute true}}))
                                       (true? (async/solo-mode return-mx :pause))
                                       (true? (async/unmix return-mx return-in))
                                       (true? (async/unmix-all return-mx))
                                       (true? (async/admix* return-mx return-in))
                                       (true? (async/toggle* return-mx {return-in {:mute false}}))
                                       (true? (async/solo-mode* return-mx :mute))
                                       (true? (async/unmix* return-mx return-in))
                                       (true? (async/unmix-all* return-mx))]]
                   (async/admix mx x)
                   (async/admix mx y)
                   (async/toggle mx {x {:mute true}})
                   (async/>! x :x-muted)
                   (async/>! y :y-live)
                   (let [muted [(async/<! mix-out) (async/poll! mix-out)]]
                     (async/close! source)
                     (async/close! pub-source)
                     (async/close! return-out)
                     (async/admix return-mx return-in)
                     (async/>! return-in :shutdown)
                     (async/close! mix-out)
                     (async/>! y :shutdown)
                     (async/<! (async/timeout 1))
                     [[:mult [first-pair left-only]]
                      [:pub  [(mapv :value published) unsubbed]]
                      [:mix  [return-contracts muted]]]))))))))))

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
