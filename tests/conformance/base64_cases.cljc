;; Portable clojure.data.codec.base64/basilisp.data.codec.base64 cases. This
;; fixture intentionally locks data.codec's permissive decoder behavior: invalid
;; alphabet bytes decode as zero bits, incomplete trailing input is ignored when
;; the computed output length does not reach it, and length helpers are plain
;; arithmetic rather than validators.

(ns conformance.base64-cases
  #?(:clj (:require [clojure.data.codec.base64 :as b64])
     :lpy (:require [clojure.data.codec.base64 :as b64]))
  #?(:clj (:import [java.io ByteArrayInputStream ByteArrayOutputStream])
     :lpy (:import io)))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn byte-array* [xs]
  (byte-array (map unchecked-byte xs)))

(defn unsigned-bytes [bs]
  (vec (map #(bit-and 0xff %) bs)))

(defn ascii [bs]
  #?(:clj (String. bs "US-ASCII")
     :lpy (.decode (python/bytes bs) "ascii")))

(defn ascii-bytes [s]
  #?(:clj (.getBytes s "US-ASCII")
     :lpy (.encode s "ascii")))

(defn input-stream [bs]
  #?(:clj (ByteArrayInputStream. bs)
     :lpy (io/BytesIO (python/bytes bs))))

(defn output-stream []
  #?(:clj (ByteArrayOutputStream.)
     :lpy (io/BytesIO)))

(defn output-bytes [out]
  #?(:clj (.toByteArray out)
     :lpy (.getvalue out)))

(defn errors? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _ true)))

(defn decoded-or-error [s]
  (let [bs (ascii-bytes s)]
    (try
      {:error? false
       :pad-error? (errors? #(b64/pad-length bs 0 (count bs)))
       :pad (when-not (errors? #(b64/pad-length bs 0 (count bs)))
              (b64/pad-length bs 0 (count bs)))
       :bytes (unsigned-bytes (b64/decode bs))}
      (catch #?(:clj Throwable :lpy python/Exception) _
        {:error? true}))))

(emit-case :public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.data.codec.base64
                                                :lpy 'basilisp.data.codec.base64))))))

(emit-case :length-arithmetic
           {:enc (mapv (fn [n] [n (b64/enc-length n)])
                       [-5 -1 0 1 2 3 4 5 6 7 8 9 10])
            :dec (mapv (fn [[length pad]]
                         [length pad (b64/dec-length length pad)])
                       [[-5 0] [-1 0] [0 0] [0 1] [0 2]
                        [1 0] [1 2] [3 2] [4 -1] [4 0]
                        [4 1] [4 2] [4 3] [8 0] [8 2]])})

(emit-case :known-vectors
           (mapv (fn [[plain encoded]]
                   (let [plain-bytes (byte-array* plain)
                         encoded-bytes (ascii-bytes encoded)]
                     {:plain plain
                      :encoded (ascii (b64/encode plain-bytes))
                      :decoded (unsigned-bytes (b64/decode encoded-bytes))
                      :pad (b64/pad-length encoded-bytes 0 (count encoded-bytes))}))
                 [[[102] "Zg=="]
                  [[102 111] "Zm8="]
                  [[102 111 111] "Zm9v"]
                  [[102 111 111 98] "Zm9vYg=="]
                  [[102 111 111 98 97] "Zm9vYmE="]
                  [[102 111 111 98 97 114] "Zm9vYmFy"]
                  [[0 1 2 253 254 255] "AAEC/f7/"]]))

(emit-case :offsets-and-mutable-destinations
           (let [source (byte-array* [120 120 102 111 111 98 97 114 121 121])
                 encoded (b64/encode source 2 6)
                 enc-dest (byte-array (b64/enc-length 6))
                 dec-dest (byte-array 6)
                 enc-written (b64/encode! source 2 6 enc-dest)
                 dec-written (b64/decode! enc-dest 0 8 dec-dest)]
             {:encoded (ascii encoded)
              :enc-written enc-written
              :enc-dest (ascii enc-dest)
              :dec-written dec-written
              :dec-dest (unsigned-bytes dec-dest)
              :zero-offset-decode (unsigned-bytes (b64/decode source 10 0))}))

(emit-case :permissive-decoding
           (into {}
                 (map (fn [s] [s (decoded-or-error s)]))
                 ["" "A" "AA" "AAA" "AAAA" "AAAAA" "abc" "abcd"
                  "!!!!" "Zg=a" "=" "==" "===" "====" "A=" "A=="
                  "A===" "AA=" "AA==" "AAA=" "AAA=="]))

(defn transfer-encode [bytes buffer-size]
  (let [out (output-stream)]
    (try
      (b64/encoding-transfer (input-stream bytes) out :buffer-size buffer-size)
      {:error? false :out (ascii (output-bytes out))}
      (catch #?(:clj Throwable :lpy python/Exception) _
        {:error? true :out (ascii (output-bytes out))}))))

(defn transfer-decode [encoded buffer-size]
  (let [out (output-stream)]
    (try
      (b64/decoding-transfer (input-stream (ascii-bytes encoded)) out
                             :buffer-size buffer-size)
      {:error? false :out (unsigned-bytes (output-bytes out))}
      (catch #?(:clj Throwable :lpy python/Exception) _
        {:error? true :out (unsigned-bytes (output-bytes out))}))))

(emit-case :transfer-semantics
           {:encode (mapv (fn [size]
                            [size (transfer-encode (ascii-bytes "abcdef") size)])
                          [0 1 2 3 4 5 6 7 8 9 12])
            :decode (mapv (fn [size]
                            [size (transfer-decode "AAAA" size)])
                          [0 1 2 3 4 5 8 12])
            :permissive-tail (transfer-decode "AAAAA" 4)})

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-bytes [seed size]
  (loop [remaining size
         seed seed
         result []]
    (if (zero? remaining)
      result
      (let [next (next-seed seed)]
        (recur (dec remaining)
               next
               (conj result (mod next 256)))))))

(emit-case :seeded-round-trips
           (loop [remaining 96
                  seed 12648430
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     prefix (seeded-bytes s1 (mod s1 9))
                     payload (seeded-bytes s2 (mod s2 257))
                     suffix (seeded-bytes (next-seed s2) (mod (next-seed s2) 9))
                     source (byte-array* (concat prefix payload suffix))
                     encoded (b64/encode source (count prefix) (count payload))
                     decoded (b64/decode encoded)
                     out (byte-array (count payload))
                     written (b64/decode! encoded 0 (count encoded) out)]
                 (recur (dec remaining)
                        s2
                        (conj result {:size (count payload)
                                      :encoded-length (count encoded)
                                      :roundtrip? (= payload (unsigned-bytes decoded))
                                      :decode-written written
                                      :decode-into? (= payload (unsigned-bytes out))}))))))
