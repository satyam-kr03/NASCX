/****************************************************************************
** Meta object code from reading C++ file 'logbuffer.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "logbuffer.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'logbuffer.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__LogBuffer_t {
    uint offsetsAndSizes[18];
    char stringdata0[26];
    char stringdata1[14];
    char stringdata2[1];
    char stringdata3[18];
    char stringdata4[6];
    char stringdata5[13];
    char stringdata6[17];
    char stringdata7[15];
    char stringdata8[15];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__LogBuffer_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__LogBuffer_t qt_meta_stringdata_omnetpp__qtenv__LogBuffer = {
    {
        QT_MOC_LITERAL(0, 25),  // "omnetpp::qtenv::LogBuffer"
        QT_MOC_LITERAL(26, 13),  // "logEntryAdded"
        QT_MOC_LITERAL(40, 0),  // ""
        QT_MOC_LITERAL(41, 17),  // "LogBuffer::Entry*"
        QT_MOC_LITERAL(59, 5),  // "entry"
        QT_MOC_LITERAL(65, 12),  // "logLineAdded"
        QT_MOC_LITERAL(78, 16),  // "messageSendAdded"
        QT_MOC_LITERAL(95, 14),  // "entryDiscarded"
        QT_MOC_LITERAL(110, 14)   // "discardedEntry"
    },
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
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__LogBuffer[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       4,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       4,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   38,    2, 0x06,    1 /* Public */,
       5,    1,   41,    2, 0x06,    3 /* Public */,
       6,    1,   44,    2, 0x06,    5 /* Public */,
       7,    1,   47,    2, 0x06,    7 /* Public */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    8,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::LogBuffer::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__LogBuffer.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__LogBuffer,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__LogBuffer_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<LogBuffer, std::true_type>,
        // method 'logEntryAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>,
        // method 'logLineAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>,
        // method 'messageSendAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>,
        // method 'entryDiscarded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::LogBuffer::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<LogBuffer *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->logEntryAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 1: _t->logLineAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 2: _t->messageSendAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 3: _t->entryDiscarded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (LogBuffer::*)(LogBuffer::Entry * );
            if (_t _q_method = &LogBuffer::logEntryAdded; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (LogBuffer::*)(LogBuffer::Entry * );
            if (_t _q_method = &LogBuffer::logLineAdded; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (LogBuffer::*)(LogBuffer::Entry * );
            if (_t _q_method = &LogBuffer::messageSendAdded; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 2;
                return;
            }
        }
        {
            using _t = void (LogBuffer::*)(LogBuffer::Entry * );
            if (_t _q_method = &LogBuffer::entryDiscarded; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 3;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::LogBuffer::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::LogBuffer::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__LogBuffer.stringdata0))
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
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 4)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 4;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::LogBuffer::logEntryAdded(LogBuffer::Entry * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void omnetpp::qtenv::LogBuffer::logLineAdded(LogBuffer::Entry * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}

// SIGNAL 2
void omnetpp::qtenv::LogBuffer::messageSendAdded(LogBuffer::Entry * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 2, _a);
}

// SIGNAL 3
void omnetpp::qtenv::LogBuffer::entryDiscarded(LogBuffer::Entry * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 3, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
