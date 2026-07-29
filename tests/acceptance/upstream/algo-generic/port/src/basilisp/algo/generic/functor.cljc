;; Source-level acceptance port of clojure.algo.generic.functor.

(ns
  ^{:author "Konrad Hinsen"
    :doc "Generic functor interface (fmap)"}
  basilisp.algo.generic.functor)

(def function-type #?(:clj clojure.lang.IFn :lpy (type (fn [_] nil))))
(def list-type #?(:clj clojure.lang.IPersistentList :lpy basilisp.lang.interfaces/IPersistentList))
(def vector-type #?(:clj clojure.lang.IPersistentVector :lpy basilisp.lang.interfaces/IPersistentVector))
(def map-type #?(:clj clojure.lang.IPersistentMap :lpy basilisp.lang.interfaces/IPersistentMap))
(def set-type #?(:clj clojure.lang.IPersistentSet :lpy basilisp.lang.interfaces/IPersistentSet))
(def seq-type #?(:clj clojure.lang.ISeq :lpy basilisp.lang.interfaces/ISeq))
(def future-type #?(:clj java.util.concurrent.Future :lpy basilisp.lang.futures/Future))
(def delay-type #?(:clj clojure.lang.Delay :lpy basilisp.lang.delay/Delay))

(defmulti fmap
  "Applies function f to each item in s and returns the same kind of structure."
  {:arglists '([f s])}
  (fn [_ s] (type s)))

(defmethod fmap list-type [f v]
  (map f v))

(defmethod fmap vector-type [f v]
  (into (empty v) (map f v)))

(defmethod fmap map-type [f m]
  (into (empty m) (for [[k v] m] [k (f v)])))

(defmethod fmap set-type [f s]
  (into (empty s) (map f s)))

(defmethod fmap function-type [f f-or-fn]
  (comp f f-or-fn))

(prefer-method fmap vector-type function-type)
(prefer-method fmap map-type function-type)
(prefer-method fmap set-type function-type)
(prefer-method fmap list-type seq-type)

(defmethod fmap seq-type [f s]
  (map f s))

(defmethod fmap future-type [f o]
  (future (f @o)))

(defmethod fmap delay-type [f d]
  (delay (f @d)))

(defmethod fmap nil [_ _]
  nil)
