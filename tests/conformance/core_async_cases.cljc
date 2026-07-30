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
     to-chan! onto-chan! merge split take
     into reduce transduce
     mult tap untap untap-all
     pub sub unsub unsub-all
     mix admix unmix unmix-all
     toggle solo-mode})

(def unsupported-parking-and-blocking-publics
  '#{go go-loop <! >! alt!
     <!! >!! alts!! thread thread-call
     pipeline-async pipeline-blocking})

(defn current-publics []
  (set (keys (ns-publics 'clojure.core.async))))

(defn supported-public-surface []
  {:supported-present?   (every? (current-publics) supported-non-go-publics)
   :unsupported-absent-in-basilisp?  #?(:clj true
                            :lpy (not-any? (current-publics)
                                           unsupported-parking-and-blocking-publics))})

#?(:clj
   (defn to-chan-roundtrip []
     (let [channel (async/to-chan! [1 2 3])]
       [(async/<!! channel)
        (async/<!! channel)
        (async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync to-chan-roundtrip []
     (let [channel (async/to-chan! [1 2 3])]
       [(await (async/take! channel))
        (await (async/take! channel))
        (await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn onto-chan-roundtrip []
     (let [channel    (async/chan 2)
           completion (async/onto-chan! channel [:first :second])]
       (async/<!! completion)
       [(async/<!! channel)
        (async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync onto-chan-roundtrip []
     (let [channel    (async/chan 2)
           completion (async/onto-chan! channel [:first :second])]
       (await (async/take! completion))
       [(await (async/take! channel))
        (await (async/take! channel))
        (await (async/take! channel))])))

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

(emit-case :core-async-public-surface
           (supported-public-surface))

(emit-case :core-async-buffers
           #?(:clj [(fixed-buffer-roundtrip)
                    (sliding-buffer-roundtrip)
                    (dropping-buffer-roundtrip)]
              :lpy [(asyncio/run (fixed-buffer-roundtrip))
                    (asyncio/run (sliding-buffer-roundtrip))
                    (asyncio/run (dropping-buffer-roundtrip))]))

(emit-case :core-async-close-and-nil
           #?(:clj [(close-drains-buffer-roundtrip)
                    (nil-put-rejected?)]
              :lpy [(asyncio/run (close-drains-buffer-roundtrip))
                    (asyncio/run (nil-put-rejected?))]))

(emit-case :core-async-selection-timeout-pipe-pipeline
           #?(:clj [(alts-priority-and-default-roundtrip)
                    (timeout-roundtrip)
                    (pipe-roundtrip)
                    (pipeline-roundtrip)]
              :lpy [(asyncio/run (alts-priority-and-default-roundtrip))
                    (asyncio/run (timeout-roundtrip))
                    (asyncio/run (pipe-roundtrip))
                    (asyncio/run (pipeline-roundtrip))]))

(emit-case :core-async-collection-combinators
           #?(:clj [(to-chan-roundtrip)
                    (onto-chan-roundtrip)
                    (merge-roundtrip)
                    (split-roundtrip)
                    (take-roundtrip)
                    (fold-roundtrip)]
              :lpy [(asyncio/run (to-chan-roundtrip))
                    (asyncio/run (onto-chan-roundtrip))
                    (asyncio/run (merge-roundtrip))
                    (asyncio/run (split-roundtrip))
                    (asyncio/run (take-roundtrip))
                    (asyncio/run (fold-roundtrip))]))

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
