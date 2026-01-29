/****************************************************************************
** Meta object code from reading C++ file 'textviewerproviders.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "textviewerproviders.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'textviewerproviders.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider_t {
    uint offsetsAndSizes[14];
    char stringdata0[42];
    char stringdata1[12];
    char stringdata2[1];
    char stringdata3[15];
    char stringdata4[18];
    char stringdata5[11];
    char stringdata6[18];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider_t qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider = {
    {
        QT_MOC_LITERAL(0, 41),  // "omnetpp::qtenv::TextViewerCon..."
        QT_MOC_LITERAL(42, 11),  // "textChanged"
        QT_MOC_LITERAL(54, 0),  // ""
        QT_MOC_LITERAL(55, 14),  // "linesDiscarded"
        QT_MOC_LITERAL(70, 17),  // "numDiscardedLines"
        QT_MOC_LITERAL(88, 10),  // "linesAdded"
        QT_MOC_LITERAL(99, 17)   // "statusTextChanged"
    },
    "omnetpp::qtenv::TextViewerContentProvider",
    "textChanged",
    "",
    "linesDiscarded",
    "numDiscardedLines",
    "linesAdded",
    "statusTextChanged"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__TextViewerContentProvider[] = {

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
       1,    0,   38,    2, 0x06,    1 /* Public */,
       3,    1,   39,    2, 0x06,    2 /* Public */,
       5,    0,   42,    2, 0x06,    4 /* Public */,
       6,    0,   43,    2, 0x06,    5 /* Public */,

 // signals: parameters
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,    4,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::TextViewerContentProvider::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__TextViewerContentProvider,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<TextViewerContentProvider, std::true_type>,
        // method 'textChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'linesDiscarded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'linesAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'statusTextChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::TextViewerContentProvider::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<TextViewerContentProvider *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->textChanged(); break;
        case 1: _t->linesDiscarded((*reinterpret_cast< std::add_pointer_t<int>>(_a[1]))); break;
        case 2: _t->linesAdded(); break;
        case 3: _t->statusTextChanged(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (TextViewerContentProvider::*)();
            if (_t _q_method = &TextViewerContentProvider::textChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (TextViewerContentProvider::*)(int );
            if (_t _q_method = &TextViewerContentProvider::linesDiscarded; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (TextViewerContentProvider::*)();
            if (_t _q_method = &TextViewerContentProvider::linesAdded; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 2;
                return;
            }
        }
        {
            using _t = void (TextViewerContentProvider::*)();
            if (_t _q_method = &TextViewerContentProvider::statusTextChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 3;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::TextViewerContentProvider::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::TextViewerContentProvider::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__TextViewerContentProvider.stringdata0))
        return static_cast<void*>(this);
    return QObject::qt_metacast(_clname);
}

int omnetpp::qtenv::TextViewerContentProvider::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
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
void omnetpp::qtenv::TextViewerContentProvider::textChanged()
{
    QMetaObject::activate(this, &staticMetaObject, 0, nullptr);
}

// SIGNAL 1
void omnetpp::qtenv::TextViewerContentProvider::linesDiscarded(int _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}

// SIGNAL 2
void omnetpp::qtenv::TextViewerContentProvider::linesAdded()
{
    QMetaObject::activate(this, &staticMetaObject, 2, nullptr);
}

// SIGNAL 3
void omnetpp::qtenv::TextViewerContentProvider::statusTextChanged()
{
    QMetaObject::activate(this, &staticMetaObject, 3, nullptr);
}
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider_t {
    uint offsetsAndSizes[2];
    char stringdata0[45];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider_t qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider = {
    {
        QT_MOC_LITERAL(0, 44)   // "omnetpp::qtenv::LineFiltering..."
    },
    "omnetpp::qtenv::LineFilteringContentProvider"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__LineFilteringContentProvider[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       0,    0, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::LineFilteringContentProvider::staticMetaObject = { {
    QMetaObject::SuperData::link<TextViewerContentProvider::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__LineFilteringContentProvider,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<LineFilteringContentProvider, std::true_type>
    >,
    nullptr
} };

void omnetpp::qtenv::LineFilteringContentProvider::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    (void)_o;
    (void)_id;
    (void)_c;
    (void)_a;
}

const QMetaObject *omnetpp::qtenv::LineFilteringContentProvider::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::LineFilteringContentProvider::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__LineFilteringContentProvider.stringdata0))
        return static_cast<void*>(this);
    return TextViewerContentProvider::qt_metacast(_clname);
}

int omnetpp::qtenv::LineFilteringContentProvider::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = TextViewerContentProvider::qt_metacall(_c, _id, _a);
    return _id;
}
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider_t {
    uint offsetsAndSizes[2];
    char stringdata0[48];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider_t qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider = {
    {
        QT_MOC_LITERAL(0, 47)   // "omnetpp::qtenv::StringTextVie..."
    },
    "omnetpp::qtenv::StringTextViewerContentProvider"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__StringTextViewerContentProvider[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       0,    0, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::StringTextViewerContentProvider::staticMetaObject = { {
    QMetaObject::SuperData::link<TextViewerContentProvider::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__StringTextViewerContentProvider,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<StringTextViewerContentProvider, std::true_type>
    >,
    nullptr
} };

void omnetpp::qtenv::StringTextViewerContentProvider::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    (void)_o;
    (void)_id;
    (void)_c;
    (void)_a;
}

const QMetaObject *omnetpp::qtenv::StringTextViewerContentProvider::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::StringTextViewerContentProvider::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__StringTextViewerContentProvider.stringdata0))
        return static_cast<void*>(this);
    return TextViewerContentProvider::qt_metacast(_clname);
}

int omnetpp::qtenv::StringTextViewerContentProvider::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = TextViewerContentProvider::qt_metacall(_c, _id, _a);
    return _id;
}
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider_t {
    uint offsetsAndSizes[18];
    char stringdata0[44];
    char stringdata1[16];
    char stringdata2[1];
    char stringdata3[18];
    char stringdata4[6];
    char stringdata5[15];
    char stringdata6[19];
    char stringdata7[17];
    char stringdata8[15];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider_t qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider = {
    {
        QT_MOC_LITERAL(0, 43),  // "omnetpp::qtenv::ModuleOutputC..."
        QT_MOC_LITERAL(44, 15),  // "onLogEntryAdded"
        QT_MOC_LITERAL(60, 0),  // ""
        QT_MOC_LITERAL(61, 17),  // "LogBuffer::Entry*"
        QT_MOC_LITERAL(79, 5),  // "entry"
        QT_MOC_LITERAL(85, 14),  // "onLogLineAdded"
        QT_MOC_LITERAL(100, 18),  // "onMessageSendAdded"
        QT_MOC_LITERAL(119, 16),  // "onEntryDiscarded"
        QT_MOC_LITERAL(136, 14)   // "discardedEntry"
    },
    "omnetpp::qtenv::ModuleOutputContentProvider",
    "onLogEntryAdded",
    "",
    "LogBuffer::Entry*",
    "entry",
    "onLogLineAdded",
    "onMessageSendAdded",
    "onEntryDiscarded",
    "discardedEntry"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__ModuleOutputContentProvider[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       4,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   38,    2, 0x09,    1 /* Protected */,
       5,    1,   41,    2, 0x09,    3 /* Protected */,
       6,    1,   44,    2, 0x09,    5 /* Protected */,
       7,    1,   47,    2, 0x09,    7 /* Protected */,

 // slots: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, 0x80000000 | 3,    8,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::ModuleOutputContentProvider::staticMetaObject = { {
    QMetaObject::SuperData::link<TextViewerContentProvider::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__ModuleOutputContentProvider,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<ModuleOutputContentProvider, std::true_type>,
        // method 'onLogEntryAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>,
        // method 'onLogLineAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>,
        // method 'onMessageSendAdded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>,
        // method 'onEntryDiscarded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<LogBuffer::Entry *, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::ModuleOutputContentProvider::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ModuleOutputContentProvider *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->onLogEntryAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 1: _t->onLogLineAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 2: _t->onMessageSendAdded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        case 3: _t->onEntryDiscarded((*reinterpret_cast< std::add_pointer_t<LogBuffer::Entry*>>(_a[1]))); break;
        default: ;
        }
    }
}

const QMetaObject *omnetpp::qtenv::ModuleOutputContentProvider::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::ModuleOutputContentProvider::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__ModuleOutputContentProvider.stringdata0))
        return static_cast<void*>(this);
    return TextViewerContentProvider::qt_metacast(_clname);
}

int omnetpp::qtenv::ModuleOutputContentProvider::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = TextViewerContentProvider::qt_metacall(_c, _id, _a);
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
QT_WARNING_POP
QT_END_MOC_NAMESPACE
