/****************************************************************************
** Meta object code from reading C++ file 'logbuffer.h'
**
** Created by: The Qt Meta Object Compiler version 69 (Qt 6.9.0)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include "logbuffer.h"
#include <QtCore/qmetatype.h>

#include <QtCore/qtmochelpers.h>

#include <memory>


#include <QtCore/qxptype_traits.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'logbuffer.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 69
#error "This file was generated using the moc from 6.9.0. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
QT_WARNING_DISABLE_GCC("-Wuseless-cast")
namespace {
struct qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t {};
} // unnamed namespace

template <> constexpr inline auto omnetpp::qtenv::LogBuffer::qt_create_metaobjectdata<qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t>()
{
    namespace QMC = QtMocConstants;
    QtMocHelpers::StringRefStorage qt_stringData {
        "omnetpp::qtenv::LogBuffer",
        "logEntryAdded",
        "",
        "LogBuffer::Entry*",
        "entry",
        "logLineAdded",
        "messageSendAdded",
        "entryDiscarded",
        "discardedEntry"
    };

    QtMocHelpers::UintData qt_methods {
        // Signal 'logEntryAdded'
        QtMocHelpers::SignalData<void(LogBuffer::Entry *)>(1, 2, QMC::AccessPublic, QMetaType::Void, {{
            { 0x80000000 | 3, 4 },
        }}),
        // Signal 'logLineAdded'
        QtMocHelpers::SignalData<void(LogBuffer::Entry *)>(5, 2, QMC::AccessPublic, QMetaType::Void, {{
            { 0x80000000 | 3, 4 },
        }}),
        // Signal 'messageSendAdded'
        QtMocHelpers::SignalData<void(LogBuffer::Entry *)>(6, 2, QMC::AccessPublic, QMetaType::Void, {{
            { 0x80000000 | 3, 4 },
        }}),
        // Signal 'entryDiscarded'
        QtMocHelpers::SignalData<void(LogBuffer::Entry *)>(7, 2, QMC::AccessPublic, QMetaType::Void, {{
            { 0x80000000 | 3, 8 },
        }}),
    };
    QtMocHelpers::UintData qt_properties {
    };
    QtMocHelpers::UintData qt_enums {
    };
    return QtMocHelpers::metaObjectData<LogBuffer, qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t>(QMC::MetaObjectFlag{}, qt_stringData,
            qt_methods, qt_properties, qt_enums);
}
Q_CONSTINIT const QMetaObject omnetpp::qtenv::LogBuffer::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_staticMetaObjectStaticContent<qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t>.stringdata,
    qt_staticMetaObjectStaticContent<qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t>.data,
    qt_static_metacall,
    nullptr,
    qt_staticMetaObjectRelocatingContent<qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t>.metaTypes,
    nullptr
} };

void omnetpp::qtenv::LogBuffer::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    auto *_t = static_cast<LogBuffer *>(_o);
    if (_c == QMetaObject::InvokeMetaMethod) {
        switch (_id) {
        case 0: _t->logEntryAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 1: _t->logLineAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 2: _t->messageSendAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 3: _t->entryDiscarded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        default: ;
        }
    }
    if (_c == QMetaObject::IndexOfMethod) {
        if (QtMocHelpers::indexOfMethod<void (LogBuffer::*)(LogBuffer::Entry * )>(_a, &LogBuffer::logEntryAdded, 0))
            return;
        if (QtMocHelpers::indexOfMethod<void (LogBuffer::*)(LogBuffer::Entry * )>(_a, &LogBuffer::logLineAdded, 1))
            return;
        if (QtMocHelpers::indexOfMethod<void (LogBuffer::*)(LogBuffer::Entry * )>(_a, &LogBuffer::messageSendAdded, 2))
            return;
        if (QtMocHelpers::indexOfMethod<void (LogBuffer::*)(LogBuffer::Entry * )>(_a, &LogBuffer::entryDiscarded, 3))
            return;
    }
}

const QMetaObject *omnetpp::qtenv::LogBuffer::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::LogBuffer::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_staticMetaObjectStaticContent<qt_meta_tag_ZN7omnetpp5qtenv9LogBufferE_t>.strings))
        return static_cast<void*>(this);
    return QObject::qt_metacast(_clname);
}

int omnetpp::qtenv::LogBuffer::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QObject::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 4)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 4;
    }
    if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 4)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 4;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::LogBuffer::logEntryAdded(LogBuffer::Entry * _t1)
{
    QMetaObject::activate<void>(this, &staticMetaObject, 0, nullptr, _t1);
}

// SIGNAL 1
void omnetpp::qtenv::LogBuffer::logLineAdded(LogBuffer::Entry * _t1)
{
    QMetaObject::activate<void>(this, &staticMetaObject, 1, nullptr, _t1);
}

// SIGNAL 2
void omnetpp::qtenv::LogBuffer::messageSendAdded(LogBuffer::Entry * _t1)
{
    QMetaObject::activate<void>(this, &staticMetaObject, 2, nullptr, _t1);
}

// SIGNAL 3
void omnetpp::qtenv::LogBuffer::entryDiscarded(LogBuffer::Entry * _t1)
{
    QMetaObject::activate<void>(this, &staticMetaObject, 3, nullptr, _t1);
}
QT_WARNING_POP
