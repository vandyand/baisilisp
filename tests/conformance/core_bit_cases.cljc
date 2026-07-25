;; Portable clojure.core bit operation semantics, including JVM long shift
;; count masking and signed 64-bit overflow boundaries.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :bit-operation-edges
           {:and-not [(bit-and-not 15 3)
                      (bit-and-not 31 1 2 4)
                      (bit-and-not -1 255)]
            :clear [(bit-clear 15 1)
                    (bit-clear 1 -1)
                    (bit-clear -1 63)]
            :flip [(bit-flip 8 0)
                   (bit-flip 1 -1)
                   (bit-flip -1 63)]
            :set [(bit-set 0 5)
                  (bit-set 1 -1)
                  (bit-set 0 64)]
            :test [(bit-test 8 3)
                   (bit-test 1 -1)
                   (bit-test -1 63)]
            :not [(bit-not 0)
                  (bit-not -1)
                  (bit-not -9223372036854775808)]
            :varargs [(bit-and 15 14 13 11)
                      (bit-or 1 2 4 8)
                      (bit-xor 1 2 4 8)]})

(emit-case :bit-shift-edges
           {:left [(bit-shift-left 1 -2)
                   (bit-shift-left 1 -1)
                   (bit-shift-left 1 0)
                   (bit-shift-left 1 63)
                   (bit-shift-left 1 64)
                   (bit-shift-left 1 65)]
            :right [(bit-shift-right -8 -2)
                    (bit-shift-right -8 -1)
                    (bit-shift-right -8 0)
                    (bit-shift-right -8 1)
                    (bit-shift-right -8 63)
                    (bit-shift-right -8 64)
                    (bit-shift-right -8 65)]
            :unsigned [(unsigned-bit-shift-right -1 -1)
                       (unsigned-bit-shift-right -1 0)
                       (unsigned-bit-shift-right -1 1)
                       (unsigned-bit-shift-right -1 63)
                       (unsigned-bit-shift-right -1 64)
                       (unsigned-bit-shift-right -1 65)]})

(defn fuzz-case [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)
        s4 (next-seed s3)
        x  (unchecked-int s1)
        y  (unchecked-int s2)
        z  (unchecked-int s3)
        n  (- (mod s4 145) 72)]
    {:x x
     :y y
     :z z
     :n n
     :and (bit-and x y z)
     :or (bit-or x y z)
     :xor (bit-xor x y z)
     :and-not (bit-and-not x y z)
     :clear (bit-clear x n)
     :flip (bit-flip x n)
     :set (bit-set x n)
     :test (bit-test x n)
     :left (bit-shift-left x n)
     :right (bit-shift-right x n)
     :unsigned (unsigned-bit-shift-right x n)}))

(emit-case :seeded-bit-fuzz
           (loop [remaining 96
                  seed 195936478
                  results []]
             (if (zero? remaining)
               results
               (let [next (next-seed seed)]
                 (recur (dec remaining)
                        next
                        (conj results (fuzz-case next)))))))
