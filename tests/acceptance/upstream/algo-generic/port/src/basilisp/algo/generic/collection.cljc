;; Source-level acceptance port of clojure.algo.generic.collection.

(ns
  ^{:author "Konrad Hinsen"
    :doc "Generic collection interface"}
  basilisp.algo.generic.collection
  (:refer-clojure :exclude [assoc conj dissoc empty get into seq])
  (:require [clojure.core :as core]))

(defmulti assoc
  "Returns a new collection with updated keys."
  {:arglists '([coll & key-val-pairs])}
  (fn [coll & _] (type coll)))

(defmethod assoc :default [m & key-val-pairs]
  (apply core/assoc m key-val-pairs))

(defmulti conj
  "Returns a new collection resulting from adding all xs to coll."
  {:arglists '([coll & xs])}
  (fn [coll & _] (type coll)))

(defmethod conj :default [coll & xs]
  (apply core/conj coll xs))

(defmulti dissoc
  "Returns a new collection with keys removed."
  {:arglists '([coll & keys])}
  (fn [coll & _] (type coll)))

(defmethod dissoc :default [m & keys]
  (apply core/dissoc m keys))

(defmulti empty
  "Returns an empty collection of the same kind as the argument."
  {:arglists '([coll])}
  type)

(defmethod empty :default [coll]
  (core/empty coll))

(defmulti get
  "Returns the element of coll referred to by key."
  {:arglists '([coll key] [coll key not-found])}
  (fn [coll & _] (type coll)))

(defmethod get :default
  ([coll key] (core/get coll key))
  ([coll key not-found] (core/get coll key not-found)))

(defmulti into
  "Returns to-coll with every item of from-coll conjoined."
  {:arglists '([to from])}
  (fn [to _] (type to)))

(declare seq)
(defmethod into :default [to from]
  (reduce conj to (seq from)))

(defmulti seq
  "Returns a seq on s."
  {:arglists '([s])}
  type)

(defmethod seq :default [s]
  (core/seq s))
