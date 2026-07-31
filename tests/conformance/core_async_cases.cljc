;; Portable checks for the currently implemented non-go clojure.core.async
;; compatibility facade.

(ns conformance.core-async-cases)

#?(:clj (require '[clojure.core.async :as async])
   :lpy (require '[clojure.core.async :as async]))

#?(:lpy (import asyncio))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def supported-non-go-publics
  '#{buffer dropping-buffer sliding-buffer
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
     mult tap untap untap-all
     pub sub unsub unsub-all
     mix admix unmix unmix-all
     toggle solo-mode
     <!! >!! alts!!
     thread thread-call io-thread})

(def unsupported-parking-and-blocking-publics
  '#{go go-loop <! >! alt!})

(defn current-publics []
  (set (keys (ns-publics 'clojure.core.async))))

(defn supported-public-surface []
  {:supported-present?   (every? (current-publics) supported-non-go-publics)
   :unsupported-absent-in-basilisp?  #?(:clj true
                            :lpy (not-any? (current-publics)
                                           unsupported-parking-and-blocking-publics))})

#?(:clj
   (defn drain-channel [channel]
     (loop [acc   []
            value (async/<!! channel)]
       (if (some? value)
         (recur (conj acc value) (async/<!! channel))
         acc)))

   :lpy
   (defasync drain-channel [channel]
     (loop [acc   []
            value (await (async/take! channel))]
       (if (some? value)
         (recur (conj acc value) (await (async/take! channel)))
         acc))))

#?(:clj
   (defn put-values [channel values]
     (doseq [value values]
       (async/>!! channel value)))

   :lpy
   (defasync put-values [channel values]
     (loop [items (seq values)]
       (when items
         (await (async/put! channel (first items)))
         (recur (next items))))))

#?(:clj
   (defn to-chan-roundtrip []
     (let [channel      (async/to-chan! [1 2 3])
           alias        (async/to-chan [4 5])
           bang-alias   (async/to-chan!! [6 7])]
       [[(async/<!! channel)
         (async/<!! channel)
         (async/<!! channel)
         (async/<!! channel)]
        [(async/<!! alias)
         (async/<!! alias)
         (async/<!! alias)]
        [(async/<!! bang-alias)
         (async/<!! bang-alias)
         (async/<!! bang-alias)]]))

   :lpy
   (defasync to-chan-roundtrip []
     (let [channel      (async/to-chan! [1 2 3])
           alias        (async/to-chan [4 5])
           bang-alias   (async/to-chan!! [6 7])]
       [[(await (async/take! channel))
         (await (async/take! channel))
         (await (async/take! channel))
         (await (async/take! channel))]
        [(await (async/take! alias))
         (await (async/take! alias))
         (await (async/take! alias))]
        [(await (async/take! bang-alias))
         (await (async/take! bang-alias))
         (await (async/take! bang-alias))]])))

#?(:clj
   (defn onto-chan-roundtrip []
     (let [channel      (async/chan 2)
           completion   (async/onto-chan! channel [:first :second])
           alias        (async/chan 2)
           alias-done   (async/onto-chan alias [:third :fourth])
           bang         (async/chan 2)
           bang-done    (async/onto-chan!! bang [:fifth :sixth])]
       (async/<!! completion)
       (async/<!! alias-done)
       (async/<!! bang-done)
       [[(async/<!! channel)
         (async/<!! channel)
         (async/<!! channel)]
        [(async/<!! alias)
         (async/<!! alias)
         (async/<!! alias)]
        [(async/<!! bang)
         (async/<!! bang)
         (async/<!! bang)]]))

   :lpy
   (defasync onto-chan-roundtrip []
     (let [channel      (async/chan 2)
           completion   (async/onto-chan! channel [:first :second])
           alias        (async/chan 2)
           alias-done   (async/onto-chan alias [:third :fourth])
           bang         (async/chan 2)
           bang-done    (async/onto-chan!! bang [:fifth :sixth])]
       (await (async/take! completion))
       (await (async/take! alias-done))
       (await (async/take! bang-done))
       [[(await (async/take! channel))
         (await (async/take! channel))
         (await (async/take! channel))]
        [(await (async/take! alias))
         (await (async/take! alias))
         (await (async/take! alias))]
        [(await (async/take! bang))
         (await (async/take! bang))
         (await (async/take! bang))]])))

#?(:clj
   (defn merge-roundtrip []
     (let [first  (async/to-chan! [1 2])
           second (async/to-chan! [3])
           output (async/merge [first second] 3)]
       (sort [(async/<!! output)
              (async/<!! output)
              (async/<!! output)])))

   :lpy
   (defasync merge-roundtrip []
     (let [first  (async/to-chan! [1 2])
           second (async/to-chan! [3])
           output (async/merge [first second] 3)]
       (sort [(await (async/take! output))
              (await (async/take! output))
              (await (async/take! output))]))))

#?(:clj
   (defn split-roundtrip []
     (let [[even odd] (async/split even? (async/to-chan! [1 2 3 4]) 2 2)]
       [(async/<!! even)
        (async/<!! even)
        (async/<!! even)
        (async/<!! odd)
        (async/<!! odd)
        (async/<!! odd)]))

   :lpy
   (defasync split-roundtrip []
     (let [[even odd] (async/split even? (async/to-chan! [1 2 3 4]) 2 2)]
       [(await (async/take! even))
        (await (async/take! even))
        (await (async/take! even))
        (await (async/take! odd))
        (await (async/take! odd))
        (await (async/take! odd))])))

#?(:clj
   (defn take-roundtrip []
     (let [output (async/take 2 (async/to-chan! [1 2 3]) 2)]
       [(async/<!! output)
        (async/<!! output)
        (async/<!! output)]))

   :lpy
   (defasync take-roundtrip []
     (let [output (async/take 2 (async/to-chan! [1 2 3]) 2)]
       [(await (async/take! output))
        (await (async/take! output))
        (await (async/take! output))])))

#?(:clj
   (defn fold-roundtrip []
     [(async/<!! (async/into [] (async/to-chan! [1 2 3])))
      (async/<!! (async/reduce + 0 (async/to-chan! [1 2 3])))
      (async/<!! (async/transduce (map inc) + 0 (async/to-chan! [1 2 3])))])

   :lpy
   (defasync fold-roundtrip []
     [(await (async/take! (async/into [] (async/to-chan! [1 2 3]))))
      (await (async/take! (async/reduce + 0 (async/to-chan! [1 2 3]))))
      (await (async/take! (async/transduce (map inc) + 0 (async/to-chan! [1 2 3]))))]))

#?(:clj
   (defn promise-channel-roundtrip []
     (let [basic       (async/promise-chan)
           closed      (async/promise-chan)
           transformed (async/promise-chan (map inc))]
       [(async/>!! basic :value)
        (async/>!! basic :ignored)
        (async/<!! basic)
        (async/<!! basic)
        (do
          (async/close! closed)
          [(async/>!! closed :late)
           (async/<!! closed)])
        (async/>!! transformed 1)
        (async/<!! transformed)
        (async/<!! transformed)]))

   :lpy
   (defn promise-channel-roundtrip []
     (let [basic       (async/promise-chan)
           closed      (async/promise-chan)
           transformed (async/promise-chan (map inc))]
       [(async/>!! basic :value)
        (async/>!! basic :ignored)
        (async/<!! basic)
        (async/<!! basic)
        (do
          (async/close! closed)
          [(async/>!! closed :late)
           (async/<!! closed)])
        (async/>!! transformed 1)
        (async/<!! transformed)
        (async/<!! transformed)])))

#?(:clj
   (defn collection-wave2-roundtrip []
     (let [mapped       (async/map + [(async/to-chan [1 2 3])
                                      (async/to-chan!! [10 20 30])]
                                   3)
           mapped-short (async/map + [(async/to-chan! [1 2])
                                      (async/to-chan! [10])]
                                   2)
           partitioned  (async/partition 3 (async/to-chan! [1 2 3 4 5]) 2)
           by-key       (async/partition-by odd? (async/to-chan! [1 3 2 4 5]) 2)
           unique       (async/unique (async/to-chan! [1 1 2 2 1 1]) 2)]
       [(drain-channel mapped)
        (drain-channel mapped-short)
        (drain-channel partitioned)
        (drain-channel by-key)
        (drain-channel unique)
        [(async/unblocking-buffer? (async/buffer 1))
         (async/unblocking-buffer? (async/sliding-buffer 1))
         (async/unblocking-buffer? (async/dropping-buffer 1))]]))

   :lpy
   (defasync collection-wave2-roundtrip []
     (let [mapped       (async/map + [(async/to-chan [1 2 3])
                                      (async/to-chan!! [10 20 30])]
                                   3)
           mapped-short (async/map + [(async/to-chan! [1 2])
                                      (async/to-chan! [10])]
                                   2)
           partitioned  (async/partition 3 (async/to-chan! [1 2 3 4 5]) 2)
           by-key       (async/partition-by odd? (async/to-chan! [1 3 2 4 5]) 2)
           unique       (async/unique (async/to-chan! [1 1 2 2 1 1]) 2)]
       [(await (drain-channel mapped))
        (await (drain-channel mapped-short))
        (await (drain-channel partitioned))
        (await (drain-channel by-key))
        (await (drain-channel unique))
        [(async/unblocking-buffer? (async/buffer 1))
         (async/unblocking-buffer? (async/sliding-buffer 1))
         (async/unblocking-buffer? (async/dropping-buffer 1))]])))

#?(:clj
   (defn transform-combinators-roundtrip []
     (let [map-in      (async/to-chan! [1 2])
           map-out     (async/map< #(* 10 %) map-in)
           filter-in   (async/to-chan! [1 2 3 4])
           filter-out  (async/filter< even? filter-in 4)
           remove-in   (async/to-chan! [1 2 3 4])
           remove-out  (async/remove< even? remove-in 4)
           cat-in      (async/to-chan! [1 2])
           cat-out     (async/mapcat< (fn [value] [value (* value 10)])
                                      cat-in
                                      4)
           target-map  (async/chan 4)
           input-map   (async/map> #(* 10 %) target-map)
           target-fil  (async/chan 4)
           input-fil   (async/filter> even? target-fil)
           target-rem  (async/chan 4)
           input-rem   (async/remove> even? target-rem)
           target-cat  (async/chan 4)
           input-cat   (async/mapcat> (fn [value] [value (* value 10)])
                                      target-cat
                                      4)]
       (put-values input-map [1 2])
       (async/close! input-map)
       (let [filter-puts (vec (doall (map #(async/>!! input-fil %)
                                          [1 2 3 4])))]
         (async/close! input-fil)
         (put-values input-rem [1 2 3 4])
         (async/close! input-rem)
         (put-values input-cat [1 2])
         (async/close! input-cat)
         [(drain-channel map-out)
          (drain-channel filter-out)
          (drain-channel remove-out)
          (drain-channel cat-out)
          (drain-channel target-map)
          filter-puts
          (drain-channel target-fil)
          (drain-channel target-rem)
          (drain-channel target-cat)])))

   :lpy
   (defasync transform-combinators-roundtrip []
     (let [map-in      (async/to-chan! [1 2])
           map-out     (async/map< #(* 10 %) map-in)
           filter-in   (async/to-chan! [1 2 3 4])
           filter-out  (async/filter< even? filter-in 4)
           remove-in   (async/to-chan! [1 2 3 4])
           remove-out  (async/remove< even? remove-in 4)
           cat-in      (async/to-chan! [1 2])
           cat-out     (async/mapcat< (fn [value] [value (* value 10)])
                                      cat-in
                                      4)
           target-map  (async/chan 4)
           input-map   (async/map> #(* 10 %) target-map)
           target-fil  (async/chan 4)
           input-fil   (async/filter> even? target-fil)
           target-rem  (async/chan 4)
           input-rem   (async/remove> even? target-rem)
           target-cat  (async/chan 4)
           input-cat   (async/mapcat> (fn [value] [value (* value 10)])
                                      target-cat
                                      4)]
       (await (put-values input-map [1 2]))
       (async/close! input-map)
       (let [filter-puts (doall [(await (async/put! input-fil 1))
                                 (await (async/put! input-fil 2))
                                 (await (async/put! input-fil 3))
                                 (await (async/put! input-fil 4))])]
         (async/close! input-fil)
         (await (put-values input-rem [1 2 3 4]))
         (async/close! input-rem)
         (await (put-values input-cat [1 2]))
         (async/close! input-cat)
         [(await (drain-channel map-out))
          (await (drain-channel filter-out))
          (await (drain-channel remove-out))
          (await (drain-channel cat-out))
          (await (drain-channel target-map))
          filter-puts
          (await (drain-channel target-fil))
          (await (drain-channel target-rem))
          (await (drain-channel target-cat))]))))

#?(:clj
   (defn fixed-buffer-roundtrip []
     (let [channel (async/chan (async/buffer 2))]
       (async/>!! channel :first)
       (async/>!! channel :second)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync fixed-buffer-roundtrip []
     (let [channel (async/chan (async/buffer 2))]
       (await (async/put! channel :first))
       (await (async/put! channel :second))
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn sliding-buffer-roundtrip []
     (let [channel (async/chan (async/sliding-buffer 2))]
       (async/>!! channel :first)
       (async/>!! channel :second)
       (async/>!! channel :third)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync sliding-buffer-roundtrip []
     (let [channel (async/chan (async/sliding-buffer 2))]
       (await (async/put! channel :first))
       (await (async/put! channel :second))
       (await (async/put! channel :third))
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn dropping-buffer-roundtrip []
     (let [channel (async/chan (async/dropping-buffer 2))]
       (async/>!! channel :first)
       (async/>!! channel :second)
       (async/>!! channel :third)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync dropping-buffer-roundtrip []
     (let [channel (async/chan (async/dropping-buffer 2))]
       (await (async/put! channel :first))
       (await (async/put! channel :second))
       (await (async/put! channel :third))
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn channel-transducer-roundtrip []
     (let [fanned      (async/chan 8 (mapcat (fn [value] [value (* value 10)])))
           filtered    (async/chan 4 (filter even?))
           partitioned (async/chan 4 (partition-all 2))]
       (async/>!! fanned 1)
       (async/>!! fanned 2)
       (async/close! fanned)
       (async/>!! filtered 1)
       (async/>!! filtered 2)
       (async/>!! filtered 3)
       (async/>!! filtered 4)
       (async/close! filtered)
       (async/>!! partitioned 1)
       (async/>!! partitioned 2)
       (async/>!! partitioned 3)
       (async/close! partitioned)
       [[(async/<!! fanned)
         (async/<!! fanned)
         (async/<!! fanned)
         (async/<!! fanned)
         (async/<!! fanned)]
        [(async/<!! filtered)
         (async/<!! filtered)
         (async/<!! filtered)]
        [(vec (async/<!! partitioned))
         (vec (async/<!! partitioned))
         (async/<!! partitioned)]]))

   :lpy
   (defasync channel-transducer-roundtrip []
     (let [fanned      (async/chan 8 (mapcat (fn [value] [value (* value 10)])))
           filtered    (async/chan 4 (filter even?))
           partitioned (async/chan 4 (partition-all 2))]
       (await (async/put! fanned 1))
       (await (async/put! fanned 2))
       (async/close! fanned)
       (await (async/put! filtered 1))
       (await (async/put! filtered 2))
       (await (async/put! filtered 3))
       (await (async/put! filtered 4))
       (async/close! filtered)
       (await (async/put! partitioned 1))
       (await (async/put! partitioned 2))
       (await (async/put! partitioned 3))
       (async/close! partitioned)
       [[(await (async/take! fanned))
         (await (async/take! fanned))
         (await (async/take! fanned))
         (await (async/take! fanned))
         (await (async/take! fanned))]
        [(await (async/take! filtered))
         (await (async/take! filtered))
         (await (async/take! filtered))]
        [(vec (await (async/take! partitioned)))
         (vec (await (async/take! partitioned)))
         (await (async/take! partitioned))]])))

#?(:clj
   (defn channel-transducer-completion-roundtrip []
     (let [limited (async/chan 4 (take 2))
           handled (async/chan 4
                               (map (fn [value]
                                      (if (even? value)
                                        (throw (ex-info "bad" {}))
                                        value)))
                               (fn [_] :handled))
           dropped (async/chan 4
                               (map (fn [value]
                                      (if (even? value)
                                        (throw (ex-info "bad" {}))
                                        value)))
                               (fn [_] nil))
           puts    [(async/>!! limited :first)
                    (async/>!! limited :second)
                    (async/>!! limited :third)]]
       (async/>!! handled 1)
       (async/>!! dropped 1)
       (async/>!! handled 2)
       (async/>!! dropped 2)
       (async/>!! handled 3)
       (async/>!! dropped 3)
       (async/close! handled)
       (async/close! dropped)
       [puts
        [(async/<!! limited)
         (async/<!! limited)
         (async/<!! limited)]
        [(async/<!! handled)
         (async/<!! handled)
         (async/<!! handled)
         (async/<!! handled)]
        [(async/<!! dropped)
         (async/<!! dropped)
         (async/<!! dropped)]]))

   :lpy
   (defasync channel-transducer-completion-roundtrip []
     (let [limited (async/chan 4 (take 2))
           handled (async/chan 4
                               (map (fn [value]
                                      (if (even? value)
                                        (throw (ex-info "bad" {}))
                                        value)))
                               (fn [_] :handled))
           dropped (async/chan 4
                               (map (fn [value]
                                      (if (even? value)
                                        (throw (ex-info "bad" {}))
                                        value)))
                               (fn [_] nil))
           puts    [(await (async/put! limited :first))
                    (await (async/put! limited :second))
                    (await (async/put! limited :third))]]
       (await (async/put! handled 1))
       (await (async/put! dropped 1))
       (await (async/put! handled 2))
       (await (async/put! dropped 2))
       (await (async/put! handled 3))
       (await (async/put! dropped 3))
       (async/close! handled)
       (async/close! dropped)
       [puts
        [(await (async/take! limited))
         (await (async/take! limited))
         (await (async/take! limited))]
        [(await (async/take! handled))
         (await (async/take! handled))
         (await (async/take! handled))
         (await (async/take! handled))]
        [(await (async/take! dropped))
         (await (async/take! dropped))
         (await (async/take! dropped))]])))

#?(:clj
   (defn channel-transducer-backpressure-roundtrip []
     (let [partitioned (async/chan 1 (partition-all 2))]
       (async/>!! partitioned 1)
       (async/>!! partitioned 2)
       (let [putter (future (async/>!! partitioned 3))]
         (Thread/sleep 50)
         (let [blocked-before? (not (realized? putter))
               first-output    (vec (async/<!! partitioned))
               put-result      @putter]
           (async/close! partitioned)
           [blocked-before?
            first-output
            put-result
            (vec (async/<!! partitioned))
            (async/<!! partitioned)]))))

   :lpy
   (defasync channel-transducer-backpressure-roundtrip []
     (let [partitioned (async/chan 1 (partition-all 2))]
       (await (async/put! partitioned 1))
       (await (async/put! partitioned 2))
       (let [putter (asyncio/create-task (async/put! partitioned 3))]
         (await (asyncio/sleep 0))
         (let [blocked-before? (not (.done putter))
               first-output    (vec (await (async/take! partitioned)))
               put-result      (await putter)]
           (async/close! partitioned)
           [blocked-before?
            first-output
            put-result
            (vec (await (async/take! partitioned)))
            (await (async/take! partitioned))])))))

#?(:clj
   (defn close-drains-buffer-roundtrip []
     (let [channel (async/chan 1)]
       (async/>!! channel :buffered)
       (async/close! channel)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync close-drains-buffer-roundtrip []
     (let [channel (async/chan 1)]
       (await (async/put! channel :buffered))
       (async/close! channel)
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn nil-put-rejected? []
     (let [channel (async/chan 1)]
       (try
         (async/>!! channel nil)
         false
         (catch Throwable _
           true))))

   :lpy
   (defasync nil-put-rejected? []
     (let [channel (async/chan 1)]
       (try
         (await (async/put! channel nil))
         false
         (catch Exception _
           true)))))

#?(:clj
   (defn alts-priority-and-default-roundtrip []
     (let [first  (async/chan 1)
           second (async/chan 1)]
       (async/>!! first :first)
       (async/>!! second :second)
       (let [[value selected] (async/alts!! [second first] :priority true)
             [fallback port]  (async/alts!! [(async/chan)] :default :fallback)]
         [value (identical? selected second) fallback port])))

   :lpy
   (defasync alts-priority-and-default-roundtrip []
     (let [first  (async/chan 1)
           second (async/chan 1)]
       (await (async/put! first :first))
       (await (async/put! second :second))
       (let [[value selected] (await (async/alts! [second first] :priority true))
             [fallback port]  (await (async/alts! [(async/chan)] :default :fallback))]
         [value (identical? selected second) fallback port]))))

#?(:clj
   (defn timeout-roundtrip []
     (async/<!! (async/timeout 1)))

   :lpy
   (defasync timeout-roundtrip []
     (await (async/take! (async/timeout 1)))))

#?(:clj
   (defn pipe-roundtrip []
     (let [source      (async/chan 2)
           destination (async/chan 2)]
       (async/>!! source :first)
       (async/>!! source :second)
       (async/close! source)
       (async/pipe source destination)
       [(async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)]))

   :lpy
   (defasync pipe-roundtrip []
     (let [source      (async/chan 2)
           destination (async/chan 2)]
       (await (async/put! source :first))
       (await (async/put! source :second))
       (async/close! source)
       (await (async/pipe source destination))
       [(await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))])))

#?(:clj
   (defn pipeline-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 3)]
       (async/>!! source 1)
       (async/>!! source 2)
       (async/>!! source 3)
       (async/close! source)
       (async/pipeline 2 destination (map inc) source)
       [(async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)]))

   :lpy
   (defasync pipeline-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 3)]
       (await (async/put! source 1))
       (await (async/put! source 2))
       (await (async/put! source 3))
       (async/close! source)
       (await (async/pipeline 2 destination (map inc) source))
       [(await (async/take! destination))
       (await (async/take! destination))
       (await (async/take! destination))
       (await (async/take! destination))])))

#?(:clj
   (defn pipeline-blocking-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 3)]
       (async/>!! source 1)
       (async/>!! source 2)
       (async/>!! source 3)
       (async/close! source)
       (async/pipeline-blocking 2 destination (map inc) source)
       [(async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)]))

   :lpy
   (defasync pipeline-blocking-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 3)]
       (await (async/put! source 1))
       (await (async/put! source 2))
       (await (async/put! source 3))
       (async/close! source)
       (await (async/pipeline-blocking 2 destination (map inc) source))
       [(await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))])))

#?(:clj
   (defn emit-async-pipeline-value [value out]
     (async/thread
       (Thread/sleep (* (- 4 value) 10))
       (async/>!! out value)
       (async/>!! out (* value 10))
       (async/close! out)))

   :lpy
   (defasync emit-async-pipeline-value [value out]
     (await (asyncio/sleep (/ (- 4 value) 100)))
     (await (async/put! out value))
     (await (async/put! out (* value 10)))
     (async/close! out)))

(defn async-pipeline-fn [value out]
  #?(:clj (emit-async-pipeline-value value out)
     :lpy (asyncio/create-task (emit-async-pipeline-value value out))))

#?(:clj
   (defn pipeline-async-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 8)]
       (async/>!! source 1)
       (async/>!! source 2)
       (async/>!! source 3)
       (async/close! source)
       (async/pipeline-async 2 destination async-pipeline-fn source)
       [(async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)]))

   :lpy
   (defasync pipeline-async-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 8)]
       (await (async/put! source 1))
       (await (async/put! source 2))
       (await (async/put! source 3))
       (async/close! source)
       (await (async/pipeline-async 2 destination async-pipeline-fn source))
       [(await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))])))

#?(:clj
   (defn pipeline-async-close-false-roundtrip []
     (let [source      (async/chan 1)
           destination (async/chan 2)]
       (async/>!! source 1)
       (async/close! source)
       (async/pipeline-async 1 destination async-pipeline-fn source false)
       [(async/<!! destination)
        (async/<!! destination)
        (async/poll! destination)
        (async/>!! destination :manual)]))

   :lpy
   (defasync pipeline-async-close-false-roundtrip []
     (let [source      (async/chan 1)
           destination (async/chan 2)]
       (await (async/put! source 1))
       (async/close! source)
       (await (async/pipeline-async 1 destination async-pipeline-fn source false))
       [(await (async/take! destination))
        (await (async/take! destination))
        (async/poll! destination)
        (await (async/put! destination :manual))])))

#?(:clj
   (defn mult-roundtrip []
     (let [source (async/chan 2)
           m      (async/mult source)
           left   (async/chan 2)
           right  (async/chan 2)
           left-ret?  (identical? left (async/tap m left))
           right-ret? (identical? right (async/tap m right false))]
       (async/>!! source :one)
       (let [both [(async/<!! left)
                   (async/<!! right)]]
         (async/untap m right)
         (async/>!! source :two)
         (let [left-only [(async/<!! left)
                          (async/poll! right)]]
           (async/close! source)
           (let [closed (do
                          (async/<!! left)
                          (async/poll! right))]
             [left-ret? right-ret? both left-only closed])))))

   :lpy
   (defasync mult-roundtrip []
     (let [source (async/chan 2)
           m      (async/mult source)
           left   (async/chan 2)
           right  (async/chan 2)
           left-ret?  (identical? left (async/tap m left))
           right-ret? (identical? right (async/tap m right false))]
       (await (async/put! source :one))
       (let [both [(await (async/take! left))
                   (await (async/take! right))]]
         (async/untap m right)
         (await (async/put! source :two))
         (let [left-only [(await (async/take! left))
                          (async/poll! right)]]
           (await (asyncio/sleep 0))
           (async/close! source)
           (await (:task m))
           (let [closed (do
                          (await (async/take! left))
                          (async/poll! right))]
             [left-ret? right-ret? both left-only closed]))))))

#?(:clj
   (defn pub-roundtrip []
     (let [source      (async/chan 4)
           publication (async/pub source :topic)
           alpha       (async/chan 4)
           beta        (async/chan 4)
           alpha-ret?  (identical? alpha (async/sub publication :a alpha))
           beta-ret?   (identical? beta (async/sub publication :b beta false))]
       (async/>!! source {:topic :a :value 1})
       (async/>!! source {:topic :b :value 2})
       (async/>!! source {:topic :c :value 3})
       (let [matched [(async/<!! alpha)
                      (async/<!! beta)]]
         (async/unsub publication :b beta)
         (async/>!! source {:topic :b :value 4})
         (let [unsubbed (async/poll! beta)]
           (async/close! source)
           (let [closed (do
                          (async/<!! alpha)
                          (async/poll! beta))]
             [alpha-ret? beta-ret? matched unsubbed closed])))))

   :lpy
   (defasync pub-roundtrip []
     (let [source      (async/chan 4)
           publication (async/pub source :topic)
           alpha       (async/chan 4)
           beta        (async/chan 4)
           alpha-ret?  (identical? alpha (async/sub publication :a alpha))
           beta-ret?   (identical? beta (async/sub publication :b beta false))]
       (await (async/put! source {:topic :a :value 1}))
       (await (async/put! source {:topic :b :value 2}))
       (await (async/put! source {:topic :c :value 3}))
       (let [matched [(await (async/take! alpha))
                      (await (async/take! beta))]]
         (async/unsub publication :b beta)
         (await (async/put! source {:topic :b :value 4}))
         (let [unsubbed (async/poll! beta)]
           (await (asyncio/sleep 0))
           (async/close! source)
           (await (:task publication))
           (let [closed (do
                           (await (async/take! alpha))
                          (async/poll! beta))]
             [alpha-ret? beta-ret? matched unsubbed closed]))))))

#?(:clj
   (defn mix-roundtrip []
     (let [out (async/chan 10)
           x   (async/chan 10)
           y   (async/chan 10)
           mx  (async/mix out)]
       (async/admix mx x)
       (async/admix mx y)
       (async/>!! x :x1)
       (let [basic (async/<!! out)]
         (async/toggle mx {x {:mute true}})
         (async/>!! x :x-muted)
         (async/>!! y :y-after-mute)
         (let [mute [(async/<!! out)
                     (do
                       (Thread/sleep 50)
                       (async/poll! out))]]
           (async/toggle mx {x {:mute false :pause true}})
           (async/>!! x :x-paused)
           (async/>!! y :y-after-pause)
           (let [pause-before [(async/<!! out)
                               (do
                                 (Thread/sleep 50)
                                 (async/poll! out))]]
             (async/toggle mx {x {:pause false}})
             [basic mute pause-before (async/<!! out)])))))

   :lpy
   (defasync mix-roundtrip []
     (let [out (async/chan 10)
           x   (async/chan 10)
           y   (async/chan 10)
           mx  (async/mix out)]
       (async/admix mx x)
       (async/admix mx y)
       (await (async/put! x :x1))
       (let [basic (await (async/take! out))]
         (async/toggle mx {x {:mute true}})
         (await (async/put! x :x-muted))
         (await (async/put! y :y-after-mute))
         (let [mute [(await (async/take! out))
                     (do
                       (await (asyncio/sleep 0))
                       (async/poll! out))]]
           (async/toggle mx {x {:mute false :pause true}})
           (await (async/put! x :x-paused))
           (await (async/put! y :y-after-pause))
           (let [pause-before [(await (async/take! out))
                               (do
                                 (await (asyncio/sleep 0))
                                 (async/poll! out))]]
             (async/toggle mx {x {:pause false}})
             [basic mute pause-before (await (async/take! out))]))))))

#?(:clj
   (defn mix-solo-roundtrip []
     (let [default-out (async/chan 10)
           default-x   (async/chan 10)
           default-y   (async/chan 10)
           default-mx  (async/mix default-out)]
       (async/admix default-mx default-x)
       (async/admix default-mx default-y)
       (async/toggle default-mx {default-x {:solo true}})
       (Thread/sleep 50)
       (async/>!! default-y :y-default-solo)
       (async/>!! default-x :x-default-solo)
       (let [default-solo [(async/<!! default-out)
                           (do
                             (Thread/sleep 50)
                             (async/poll! default-out))]]
         (async/toggle default-mx {default-x {:solo false}})
         (let [default-after (do
                               (Thread/sleep 50)
                               (async/poll! default-out))
               pause-out     (async/chan 10)
               pause-x       (async/chan 10)
               pause-y       (async/chan 10)
               pause-mx      (async/mix pause-out)]
           (async/admix pause-mx pause-x)
           (async/admix pause-mx pause-y)
           (async/solo-mode pause-mx :pause)
           (async/toggle pause-mx {pause-x {:solo true}})
           (Thread/sleep 50)
           (async/>!! pause-y :y-paused-solo)
           (async/>!! pause-x :x-paused-solo)
           (let [pause-solo [(async/<!! pause-out)
                             (do
                               (Thread/sleep 50)
                               (async/poll! pause-out))]]
             (async/toggle pause-mx {pause-x {:solo false}})
             [default-solo
              default-after
              pause-solo
              (async/<!! pause-out)])))))

   :lpy
   (defasync mix-solo-roundtrip []
     (let [default-out (async/chan 10)
           default-x   (async/chan 10)
           default-y   (async/chan 10)
           default-mx  (async/mix default-out)]
       (async/admix default-mx default-x)
       (async/admix default-mx default-y)
       (async/toggle default-mx {default-x {:solo true}})
       (await (asyncio/sleep 0))
       (await (async/put! default-y :y-default-solo))
       (await (async/put! default-x :x-default-solo))
       (let [default-solo [(await (async/take! default-out))
                           (do
                             (await (asyncio/sleep 0))
                             (async/poll! default-out))]]
         (async/toggle default-mx {default-x {:solo false}})
         (let [default-after (do
                               (await (asyncio/sleep 0))
                               (async/poll! default-out))
               pause-out     (async/chan 10)
               pause-x       (async/chan 10)
               pause-y       (async/chan 10)
               pause-mx      (async/mix pause-out)]
           (async/admix pause-mx pause-x)
           (async/admix pause-mx pause-y)
           (async/solo-mode pause-mx :pause)
           (async/toggle pause-mx {pause-x {:solo true}})
           (await (asyncio/sleep 0))
           (await (async/put! pause-y :y-paused-solo))
           (await (async/put! pause-x :x-paused-solo))
           (let [pause-solo [(await (async/take! pause-out))
                             (do
                               (await (asyncio/sleep 0))
                               (async/poll! pause-out))]]
             (async/toggle pause-mx {pause-x {:solo false}})
              [default-solo
               default-after
               pause-solo
               (await (async/take! pause-out))]))))))

#?(:clj
   (defn mix-toggle-add-roundtrip []
     (let [out (async/chan 10)
           x   (async/chan 10)
           mx  (async/mix out)]
       (async/toggle mx {x {:pause true}})
       (async/>!! x :added-paused)
       (let [before (do
                      (Thread/sleep 50)
                      (async/poll! out))]
         (async/toggle mx {x {:pause false}})
         [before (async/<!! out)])))

   :lpy
   (defasync mix-toggle-add-roundtrip []
     (let [out (async/chan 10)
           x   (async/chan 10)
           mx  (async/mix out)]
       (async/toggle mx {x {:pause true}})
       (await (async/put! x :added-paused))
       (let [before (do
                      (await (asyncio/sleep 0))
                      (async/poll! out))]
         (async/toggle mx {x {:pause false}})
         [before (await (async/take! out))]))))

#?(:clj
   (defn blocking-roundtrip []
     (let [channel (async/chan 1)
           first   (async/chan 1)
           second  (async/chan 1)]
       [(async/>!! channel :value)
        (async/<!! channel)
        (do
          (async/>!! first :first)
          (async/>!! second :second)
          (let [[value selected] (async/alts!! [second first] :priority true)
                [fallback port]  (async/alts!! [(async/chan)] :default :fallback)]
            [value (identical? selected second) fallback port]))]))

   :lpy
   (defn blocking-roundtrip []
     (let [channel (async/chan 1)
           first   (async/chan 1)
           second  (async/chan 1)]
       [(async/>!! channel :value)
        (async/<!! channel)
        (do
          (async/>!! first :first)
          (async/>!! second :second)
          (let [[value selected] (async/alts!! [second first] :priority true)
                [fallback port]  (async/alts!! [(async/chan)] :default :fallback)]
            [value (identical? selected second) fallback port]))])))

#?(:clj
   (defn thread-roundtrip []
     (let [from-call (async/thread-call (fn [] :thread-call-result))
           from-body (async/thread :thread-result)
           from-nil  (async/thread nil)]
       [(async/<!! from-call)
        (async/<!! from-call)
        (async/<!! from-body)
        (async/<!! from-body)
        (async/<!! from-nil)]))

   :lpy
   (defn thread-roundtrip []
     (let [from-call (async/thread-call (fn [] :thread-call-result))
           from-body (async/thread :thread-result)
           from-nil  (async/thread nil)]
       [(async/<!! from-call)
        (async/<!! from-call)
        (async/<!! from-body)
        (async/<!! from-body)
        (async/<!! from-nil)])))

#?(:clj
   (defn io-thread-roundtrip []
     (let [from-body (async/io-thread :io-thread-result)
           from-nil  (async/io-thread nil)]
       [(async/<!! from-body)
        (async/<!! from-body)
        (async/<!! from-nil)]))

   :lpy
   (defn io-thread-roundtrip []
     (let [from-body (async/io-thread :io-thread-result)
           from-nil  (async/io-thread nil)]
       [(async/<!! from-body)
        (async/<!! from-body)
        (async/<!! from-nil)])))

(emit-case :core-async-public-surface
           (supported-public-surface))

(emit-case :core-async-buffers
           #?(:clj [(fixed-buffer-roundtrip)
                    (sliding-buffer-roundtrip)
                    (dropping-buffer-roundtrip)
                    (channel-transducer-roundtrip)
                    (channel-transducer-completion-roundtrip)
                    (channel-transducer-backpressure-roundtrip)]
              :lpy [(asyncio/run (fixed-buffer-roundtrip))
                    (asyncio/run (sliding-buffer-roundtrip))
                    (asyncio/run (dropping-buffer-roundtrip))
                    (asyncio/run (channel-transducer-roundtrip))
                    (asyncio/run (channel-transducer-completion-roundtrip))
                    (asyncio/run (channel-transducer-backpressure-roundtrip))]))

(emit-case :core-async-close-and-nil
           #?(:clj [(close-drains-buffer-roundtrip)
                    (nil-put-rejected?)
                    (promise-channel-roundtrip)]
              :lpy [(asyncio/run (close-drains-buffer-roundtrip))
                    (asyncio/run (nil-put-rejected?))
                    (promise-channel-roundtrip)]))

(emit-case :core-async-selection-timeout-pipe-pipeline
           #?(:clj [(alts-priority-and-default-roundtrip)
                    (timeout-roundtrip)
                    (pipe-roundtrip)
                    (pipeline-roundtrip)
                    (pipeline-blocking-roundtrip)
                    (pipeline-async-roundtrip)
                    (pipeline-async-close-false-roundtrip)]
              :lpy [(asyncio/run (alts-priority-and-default-roundtrip))
                    (asyncio/run (timeout-roundtrip))
                    (asyncio/run (pipe-roundtrip))
                    (asyncio/run (pipeline-roundtrip))
                    (asyncio/run (pipeline-blocking-roundtrip))
                    (asyncio/run (pipeline-async-roundtrip))
                    (asyncio/run (pipeline-async-close-false-roundtrip))]))

(emit-case :core-async-collection-combinators
           #?(:clj [(to-chan-roundtrip)
                    (onto-chan-roundtrip)
                    (merge-roundtrip)
                    (split-roundtrip)
                    (take-roundtrip)
                    (fold-roundtrip)
                    (transform-combinators-roundtrip)
                    (collection-wave2-roundtrip)]
              :lpy [(asyncio/run (to-chan-roundtrip))
                    (asyncio/run (onto-chan-roundtrip))
                    (asyncio/run (merge-roundtrip))
                    (asyncio/run (split-roundtrip))
                    (asyncio/run (take-roundtrip))
                    (asyncio/run (fold-roundtrip))
                    (asyncio/run (transform-combinators-roundtrip))
                    (asyncio/run (collection-wave2-roundtrip))]))

(emit-case :core-async-routing-combinators
           #?(:clj [(mult-roundtrip)
                    (pub-roundtrip)
                    (mix-roundtrip)
                    (mix-solo-roundtrip)
                    (mix-toggle-add-roundtrip)]
              :lpy [(asyncio/run (mult-roundtrip))
                    (asyncio/run (pub-roundtrip))
                    (asyncio/run (mix-roundtrip))
                    (asyncio/run (mix-solo-roundtrip))
                    (asyncio/run (mix-toggle-add-roundtrip))]))

(emit-case :core-async-blocking-bridges
           [(blocking-roundtrip)
            (thread-roundtrip)
            (io-thread-roundtrip)])
